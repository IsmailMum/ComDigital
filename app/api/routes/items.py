from typing import Any

from fastapi import APIRouter

from app.api.dependencies import SessionDep, CurrentUser
from app.models import ItemCreate, Item, ItemPublic

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