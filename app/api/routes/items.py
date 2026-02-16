import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter

from app import crud
from app.api.dependencies import SessionDep, CurrentUser
from app.core.cache import cache_get, cache_set, cache_delete_pattern
from app.core.exceptions import ItemNotFoundError, PermissionDeniedError
from app.models import (
    ItemCreate, ItemPublic, ItemUpdate, ItemStatus, ItemCategory,
    Message, CategoryDensityResponse,
)
from app.utils import compute_category_density

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/items",
    tags=["items"]
)

# ── Cache key helpers ────────────────────────────────────────────────
ITEMS_CACHE_PREFIX = "items"


def _list_cache_key(
    user_id: uuid.UUID,
    skip: int,
    limit: int,
    status: ItemStatus | None,
    category: ItemCategory | None,
    is_superuser: bool,
) -> str:
    return (
        f"{ITEMS_CACHE_PREFIX}:list:"
        f"user={user_id}:su={is_superuser}:"
        f"skip={skip}:limit={limit}:"
        f"status={status}:cat={category}"
    )


def _detail_cache_key(user_id: uuid.UUID, item_id: uuid.UUID) -> str:
    return f"{ITEMS_CACHE_PREFIX}:detail:user={user_id}:id={item_id}"


def _density_cache_key() -> str:
    return f"{ITEMS_CACHE_PREFIX}:analytics:category-density"


async def _invalidate_items_cache(owner_id: uuid.UUID) -> None:
    """Invalidate all cached item keys related to a particular owner and global analytics."""
    await cache_delete_pattern(f"{ITEMS_CACHE_PREFIX}:list:user={owner_id}:*")
    await cache_delete_pattern(f"{ITEMS_CACHE_PREFIX}:detail:user={owner_id}:*")
    # Superuser caches may include this user's items – clear them too
    await cache_delete_pattern(f"{ITEMS_CACHE_PREFIX}:list:*su=True*")
    await cache_delete_pattern(f"{ITEMS_CACHE_PREFIX}:analytics:*")


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/", response_model=ItemPublic)
async def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    item = await crud.create_item(session=session, item_in=item_in, owner_id=current_user.id)
    await _invalidate_items_cache(current_user.id)
    logger.info("Item created: id=%s by user=%s", item.id, current_user.id)
    return item


@router.get("/", response_model=list[ItemPublic])
async def get_items(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 10,
    status: ItemStatus | None = None,
    category: ItemCategory | None = None,
) -> Any:
    cache_key = _list_cache_key(
        current_user.id, skip, limit, status, category, current_user.is_superuser
    )
    cached = await cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT for items list: user=%s", current_user.id)
        return cached

    logger.debug("Cache MISS for items list: user=%s", current_user.id)
    owner_id = None if current_user.is_superuser else current_user.id
    items = await crud.get_items(
        session=session, owner_id=owner_id, skip=skip, limit=limit,
        status=status, category=category,
    )

    items_data = [ItemPublic.model_validate(i).model_dump(mode="json") for i in items]
    await cache_set(cache_key, items_data)
    return items


@router.get("/{id}", response_model=ItemPublic)
async def get_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    cache_key = _detail_cache_key(current_user.id, id)
    cached = await cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT for item detail: id=%s", id)
        return cached

    logger.debug("Cache MISS for item detail: id=%s", id)
    item = await crud.get_item_by_id(session=session, item_id=id)
    if not item:
        logger.warning("Item not found: id=%s requested by user=%s", id, current_user.id)
        raise ItemNotFoundError()
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        logger.warning("Permission denied: user=%s tried to access item=%s", current_user.id, id)
        raise PermissionDeniedError()

    item_data = ItemPublic.model_validate(item).model_dump(mode="json")
    await cache_set(cache_key, item_data)
    return item


@router.put("/{id}", response_model=ItemPublic)
async def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    item = await crud.get_item_for_update(session=session, item_id=id)
    if not item:
        logger.warning("Item not found for update: id=%s by user=%s", id, current_user.id)
        raise ItemNotFoundError()
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        logger.warning("Permission denied: user=%s tried to update item=%s", current_user.id, id)
        raise PermissionDeniedError()
    item = await crud.update_item(session=session, db_item=item, item_in=item_in)
    await _invalidate_items_cache(item.owner_id)
    logger.info("Item updated: id=%s by user=%s", id, current_user.id)
    return item


@router.delete("/{id}")
async def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    item = await crud.get_item_for_update(session=session, item_id=id)
    if not item:
        logger.warning("Item not found for deletion: id=%s by user=%s", id, current_user.id)
        raise ItemNotFoundError()
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        logger.warning("Permission denied: user=%s tried to delete item=%s", current_user.id, id)
        raise PermissionDeniedError()
    owner_id = item.owner_id
    await crud.delete_item(session=session, item=item)
    await _invalidate_items_cache(owner_id)
    logger.info("Item deleted: id=%s by user=%s", id, current_user.id)
    return Message(message="Item deleted successfully")


@router.get("/analytics/category-density", response_model=CategoryDensityResponse)
async def get_category_density(session: SessionDep, current_user: CurrentUser) -> Any:
    cache_key = _density_cache_key()
    cached = await cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT for category density analytics")
        return cached

    logger.debug("Cache MISS for category density analytics — computing")
    results = await crud.get_category_counts(session=session)
    response = await asyncio.to_thread(compute_category_density, results)

    await cache_set(cache_key, response.model_dump(mode="json"))
    return response
