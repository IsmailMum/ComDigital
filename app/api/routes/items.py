import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlmodel import select, col

from app.api.dependencies import SessionDep, CurrentUser
from app.models import (
    ItemCreate, Item, ItemPublic, ItemUpdate, ItemStatus, ItemCategory,
    Message, CategoryDensityResponse,
)
from app.utils import compute_category_density

router = APIRouter(
    prefix="/items",
    tags=["items"]
)


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
    statement = select(Item)

    if not current_user.is_superuser:
        statement = statement.where(Item.owner_id == current_user.id)

    if status is not None:
        statement = statement.where(Item.status == status)
    if category is not None:
        statement = statement.where(Item.category == category)

    statement = statement.order_by(col(Item.created_at).desc()).offset(skip).limit(limit)
    items = (await session.execute(statement)).scalars().all()

    return items

@router.get("/{id}", response_model=ItemPublic)
async def get_item(session: SessionDep, current_user: CurrentUser, item_id: uuid.UUID) -> Any:
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
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
    statement = select(Item.category, func.count().label("count")).group_by(Item.category)
    results = (await session.execute(statement)).all()
    return await asyncio.to_thread(compute_category_density, results)