import enum
import uuid
from datetime import datetime, timezone

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import SQLModel, Field, Relationship


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class ItemStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class ItemCategory(str, enum.Enum):
    electronics = "electronics"
    clothing = "clothing"
    food = "food"
    books = "books"
    other = "other"


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)


class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None


class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    status: ItemStatus = Field(default=ItemStatus.draft)
    category: ItemCategory | None = Field(default=None)


class ItemCreate(ItemBase):
    pass


class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class CategoryDensityItem(SQLModel):
    category: str
    count: int
    percentage: float


class CategoryDensityData(SQLModel):
    total_items: int
    categories: list[CategoryDensityItem]


class CategoryDensityResponse(SQLModel):
    success: bool
    data: CategoryDensityData


class Message(SQLModel):
    message: str

