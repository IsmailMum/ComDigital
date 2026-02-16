import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlmodel import select, col

from app.api.dependencies import SessionDep, CurrentUser
from app.core.cache import cache_get, cache_set, cache_delete_pattern
from app.models import (
    ItemCreate, Item, ItemPublic, ItemUpdate, ItemStatus, ItemCategory,
    Message, CategoryDensityResponse,
)
from app.utils import compute_category_density

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
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    await session.commit()
    await session.refresh(item)
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
        return cached

    if status is not None:
        statement = statement.where(Item.status == status)
    if category is not None:
        statement = statement.where(Item.category == category)

    items_data = [ItemPublic.model_validate(i).model_dump(mode="json") for i in items]
    await cache_set(cache_key, items_data)
    return items


@router.get("/{id}", response_model=ItemPublic)
async def get_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    cache_key = _detail_cache_key(current_user.id, id)
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    item = await crud.get_item_by_id(session=session, item_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    item_data = ItemPublic.model_validate(item).model_dump(mode="json")
    await cache_set(cache_key, item_data)
    return item


@router.put("/{id}", response_model=ItemPublic)
async def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    item_id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    await _invalidate_items_cache(item.owner_id)
    return item


@router.delete("/{id}")
async def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    item = await session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    await session.delete(item)
    await session.commit()
    return Message(message="Item deleted successfully")


@router.get("/analytics/category-density", response_model=CategoryDensityResponse)
async def get_category_density(session: SessionDep, current_user: CurrentUser) -> Any:
    cache_key = _density_cache_key()
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    results = await crud.get_category_counts(session=session)
    response = await asyncio.to_thread(compute_category_density, results)

    await cache_set(cache_key, response.model_dump(mode="json"))
    return response
