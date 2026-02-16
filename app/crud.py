import uuid

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, col

from app.core.security import get_password_hash, verify_password
from app.models import (
    User, UserCreate, UserUpdateMe,
    Item, ItemCreate, ItemUpdate, ItemStatus, ItemCategory,
)



async def create_user(*, session: AsyncSession, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def get_user_by_email(*, session: AsyncSession, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    return result.scalars().first()


async def update_user(*, session: AsyncSession, db_user: User, user_in: UserUpdateMe) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


# Dummy hash to use for timing attack prevention when user is not found
# This is a bcrypt hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$2b$12$CtdxuaX/46Z9rPRG.YqqbesHuwXLohoDsYacqiKGXhnFAUOIvbTm."


async def authenticate(*, session: AsyncSession, email: str, password: str) -> User | None:
    db_user = await get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)
    return db_user


async def create_item(
    *, session: AsyncSession, item_in: ItemCreate, owner_id: uuid.UUID
) -> Item:
    item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def get_items(
    *,
    session: AsyncSession,
    owner_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 10,
    status: ItemStatus | None = None,
    category: ItemCategory | None = None,
) -> list[Item]:
    statement = select(Item)

    if owner_id is not None:
        statement = statement.where(Item.owner_id == owner_id)

    if status is not None:
        statement = statement.where(Item.status == status)
    if category is not None:
        statement = statement.where(Item.category == category)

    statement = statement.order_by(col(Item.created_at).desc()).offset(skip).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_item_by_id(*, session: AsyncSession, item_id: uuid.UUID) -> Item | None:
    return await session.get(Item, item_id)


async def get_item_for_update(*, session: AsyncSession, item_id: uuid.UUID) -> Item | None:
    """Fetch an item with a ``SELECT … FOR UPDATE`` row-level lock."""
    statement = select(Item).where(Item.id == item_id).with_for_update()
    result = await session.execute(statement)
    return result.scalars().first()


async def update_item(
    *, session: AsyncSession, db_item: Item, item_in: ItemUpdate
) -> Item:
    update_dict = item_in.model_dump(exclude_unset=True)
    db_item.sqlmodel_update(update_dict)
    session.add(db_item)
    await session.commit()
    await session.refresh(db_item)
    return db_item


async def delete_item(*, session: AsyncSession, item: Item) -> None:
    await session.delete(item)
    await session.commit()


async def get_category_counts(*, session: AsyncSession) -> list:
    statement = select(Item.category, func.count().label("count")).group_by(Item.category)
    result = await session.execute(statement)
    return list(result.all())
