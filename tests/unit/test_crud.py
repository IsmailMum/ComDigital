import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.crud import (
    create_user,
    get_user_by_email,
    update_user,
    authenticate,
    create_item,
    get_items,
    get_item_by_id,
    get_item_for_update,
    update_item,
    delete_item,
    get_category_counts,
)
from app.models import (
    User,
    UserCreate,
    UserUpdateMe,
    Item,
    ItemCreate,
    ItemUpdate,
    ItemStatus,
    ItemCategory,
)


# ── Helpers ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    return session


def _mock_execute_result(item=None, items=None, rows=None):
    scalars = MagicMock()
    scalars.first.return_value = item
    scalars.all.return_value = (
        items if items is not None else ([] if item is None else [item])
    )
    result = MagicMock()
    result.scalars.return_value = scalars
    if rows is not None:
        result.all.return_value = rows
    return result


# ── User CRUD ──────────────────────────────────────────────────────


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_creates_user_with_hashed_password(self, mock_session):
        user_create = UserCreate(
            email="new@example.com", password="strongpass123"
        )

        result = await create_user(session=mock_session, user_create=user_create)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()
        assert isinstance(result, User)
        assert result.email == "new@example.com"
        # Password should be hashed, not plain
        assert result.hashed_password != "strongpass123"
        assert result.hashed_password.startswith("$2")


class TestGetUserByEmail:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self, mock_session):
        user = User(
            id=uuid.uuid4(),
            email="found@example.com",
            hashed_password="fakehash",
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=user)
        )

        result = await get_user_by_email(session=mock_session, email="found@example.com")
        assert result is user

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session):
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=None)
        )

        result = await get_user_by_email(session=mock_session, email="nobody@example.com")
        assert result is None


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_updates_user_fields(self, mock_session):
        user = User(
            id=uuid.uuid4(),
            email="update@example.com",
            hashed_password="fakehash",
            full_name="Old Name",
        )
        user_in = UserUpdateMe(full_name="New Name")

        result = await update_user(session=mock_session, db_user=user, user_in=user_in)

        assert result.full_name == "New Name"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_successful_authentication(self, mock_session):
        from app.core.security import get_password_hash

        password = "correctpassword"
        hashed = get_password_hash(password)
        user = User(
            id=uuid.uuid4(),
            email="auth@example.com",
            hashed_password=hashed,
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=user)
        )

        result = await authenticate(
            session=mock_session, email="auth@example.com", password=password
        )
        assert result is user

    @pytest.mark.asyncio
    async def test_wrong_password_returns_none(self, mock_session):
        from app.core.security import get_password_hash

        user = User(
            id=uuid.uuid4(),
            email="auth@example.com",
            hashed_password=get_password_hash("correctpassword"),
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=user)
        )

        result = await authenticate(
            session=mock_session, email="auth@example.com", password="wrongpassword"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_none(self, mock_session):
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=None)
        )

        result = await authenticate(
            session=mock_session, email="ghost@example.com", password="whatever"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_rehashes_password_when_needed(self, mock_session):
        """When verify_password signals a rehash, the new hash should be persisted."""
        user = User(
            id=uuid.uuid4(),
            email="rehash@example.com",
            hashed_password="old_hash",
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=user)
        )

        with patch(
            "app.crud.verify_password",
            return_value=(True, "new_updated_hash"),
        ):
            result = await authenticate(
                session=mock_session, email="rehash@example.com", password="pass"
            )

        assert result is user
        assert user.hashed_password == "new_updated_hash"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()


# ── Item CRUD ──────────────────────────────────────────────────────


class TestCreateItem:
    @pytest.mark.asyncio
    async def test_creates_item_with_owner(self, mock_session):
        owner_id = uuid.uuid4()
        item_in = ItemCreate(title="Test Item", category=ItemCategory.books)

        result = await create_item(session=mock_session, item_in=item_in, owner_id=owner_id)

        assert isinstance(result, Item)
        assert result.title == "Test Item"
        assert result.owner_id == owner_id
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()


class TestGetItems:
    @pytest.mark.asyncio
    async def test_returns_items(self, mock_session):
        items = [
            Item(id=uuid.uuid4(), title=f"Item {i}", status=ItemStatus.draft, owner_id=uuid.uuid4())
            for i in range(3)
        ]
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(items=items)
        )

        result = await get_items(session=mock_session)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_filters_by_status(self, mock_session):
        items = [
            Item(id=uuid.uuid4(), title="Draft", status=ItemStatus.draft, owner_id=uuid.uuid4())
        ]
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(items=items)
        )

        result = await get_items(session=mock_session, status=ItemStatus.draft)
        assert len(result) == 1
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filters_by_category(self, mock_session):
        items = [
            Item(id=uuid.uuid4(), title="Book", status=ItemStatus.draft, category=ItemCategory.books, owner_id=uuid.uuid4())
        ]
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(items=items)
        )

        result = await get_items(session=mock_session, category=ItemCategory.books)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filters_by_owner(self, mock_session):
        owner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(items=[])
        )

        await get_items(session=mock_session, owner_id=owner_id)
        mock_session.execute.assert_awaited_once()


class TestGetItemById:
    @pytest.mark.asyncio
    async def test_returns_item(self, mock_session):
        item_id = uuid.uuid4()
        item = Item(id=item_id, title="Found", status=ItemStatus.draft, owner_id=uuid.uuid4())
        mock_session.get = AsyncMock(return_value=item)

        result = await get_item_by_id(session=mock_session, item_id=item_id)
        assert result is item

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session):
        mock_session.get = AsyncMock(return_value=None)

        result = await get_item_by_id(session=mock_session, item_id=uuid.uuid4())
        assert result is None


class TestGetItemForUpdate:
    @pytest.mark.asyncio
    async def test_returns_item_with_lock(self, mock_session):
        item = Item(id=uuid.uuid4(), title="Locked", status=ItemStatus.draft, owner_id=uuid.uuid4())
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=item)
        )

        result = await get_item_for_update(session=mock_session, item_id=item.id)
        assert result is item


class TestUpdateItem:
    @pytest.mark.asyncio
    async def test_updates_item(self, mock_session):
        item = Item(
            id=uuid.uuid4(), title="Old", description="Desc",
            status=ItemStatus.draft, category=ItemCategory.electronics,
            owner_id=uuid.uuid4(),
        )
        item_in = ItemUpdate(title="New")

        result = await update_item(session=mock_session, db_item=item, item_in=item_in)

        assert result.title == "New"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()


class TestDeleteItem:
    @pytest.mark.asyncio
    async def test_deletes_item(self, mock_session):
        item = Item(id=uuid.uuid4(), title="Bye", status=ItemStatus.draft, owner_id=uuid.uuid4())

        await delete_item(session=mock_session, item=item)

        mock_session.delete.assert_awaited_once_with(item)
        mock_session.commit.assert_awaited_once()


class TestGetCategoryCounts:
    @pytest.mark.asyncio
    async def test_returns_counts(self, mock_session):
        rows = [("electronics", 5), ("books", 3)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_category_counts(session=mock_session)
        assert result == [("electronics", 5), ("books", 3)]
