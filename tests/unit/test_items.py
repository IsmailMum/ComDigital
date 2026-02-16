import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.models import Item, ItemStatus, ItemCategory


# ── Helpers ─────────────────────────────────────────────────────────


def _mock_execute_result(item=None, items=None, rows=None):
    """Build a mock for ``(await session.execute(stmt)).scalars().first()``/``.all()``."""
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


# ── CREATE ──────────────────────────────────────────────────────────


class TestCreateItem:
    @pytest.mark.asyncio
    async def test_success(self, client: AsyncClient, mock_session: AsyncMock):
        response = await client.post(
            "/api/v1/items/",
            json={
                "title": "New Item",
                "description": "A new item",
                "status": "draft",
                "category": "electronics",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Item"
        assert data["description"] == "A new item"
        assert data["status"] == "draft"
        assert data["category"] == "electronics"
        assert "id" in data
        assert "owner_id" in data
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_title_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/items/", json={"description": "No title"}
        )
        assert response.status_code == 422


# ── READ ONE ────────────────────────────────────────────────────────


class TestGetItem:
    @pytest.mark.asyncio
    async def test_found(
        self, client: AsyncClient, mock_session: AsyncMock, user_id
    ):
        item = Item(
            id=uuid.uuid4(),
            title="Found",
            status=ItemStatus.draft,
            category=ItemCategory.electronics,
            owner_id=user_id,
        )
        mock_session.get = AsyncMock(return_value=item)

        response = await client.get(f"/api/v1/items/{item.id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Found"

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient, mock_session: AsyncMock):
        mock_session.get = AsyncMock(return_value=None)

        response = await client.get(f"/api/v1/items/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_owner_returns_403(
        self, client: AsyncClient, mock_session: AsyncMock, other_user_id
    ):
        item = Item(
            id=uuid.uuid4(),
            title="Not mine",
            status=ItemStatus.draft,
            owner_id=other_user_id,
        )
        mock_session.get = AsyncMock(return_value=item)

        response = await client.get(f"/api/v1/items/{item.id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_superuser_bypasses_ownership(
        self,
        superuser_client: AsyncClient,
        mock_session: AsyncMock,
        other_user_id,
    ):
        item = Item(
            id=uuid.uuid4(),
            title="Anyone's",
            status=ItemStatus.draft,
            owner_id=other_user_id,
        )
        mock_session.get = AsyncMock(return_value=item)

        response = await superuser_client.get(f"/api/v1/items/{item.id}")
        assert response.status_code == 200


# ── READ LIST ───────────────────────────────────────────────────────


class TestGetItems:
    @pytest.mark.asyncio
    async def test_returns_items(
        self, client: AsyncClient, mock_session: AsyncMock, user_id
    ):
        items = [
            Item(
                id=uuid.uuid4(),
                title=f"Item {i}",
                status=ItemStatus.draft,
                owner_id=user_id,
            )
            for i in range(3)
        ]
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(items=items)
        )

        response = await client.get("/api/v1/items/")
        assert response.status_code == 200
        assert len(response.json()) == 3


# ── UPDATE ──────────────────────────────────────────────────────────


class TestUpdateItem:
    @pytest.mark.asyncio
    async def test_success(
        self, client: AsyncClient, mock_session: AsyncMock, user_id
    ):
        item = Item(
            id=uuid.uuid4(),
            title="Original",
            description="Desc",
            status=ItemStatus.draft,
            category=ItemCategory.electronics,
            owner_id=user_id,
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=item)
        )

        response = await client.put(
            f"/api/v1/items/{item.id}",
            json={"title": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated"
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient, mock_session: AsyncMock):
        mock_session.execute = AsyncMock(return_value=_mock_execute_result())

        response = await client.put(
            f"/api/v1/items/{uuid.uuid4()}",
            json={"title": "X"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_owner_returns_403(
        self, client: AsyncClient, mock_session: AsyncMock, other_user_id
    ):
        item = Item(
            id=uuid.uuid4(),
            title="Not mine",
            status=ItemStatus.draft,
            owner_id=other_user_id,
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=item)
        )

        response = await client.put(
            f"/api/v1/items/{item.id}",
            json={"title": "Nope"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_superuser_can_update_any(
        self,
        superuser_client: AsyncClient,
        mock_session: AsyncMock,
        other_user_id,
    ):
        item = Item(
            id=uuid.uuid4(),
            title="Other's",
            status=ItemStatus.draft,
            category=ItemCategory.electronics,
            owner_id=other_user_id,
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=item)
        )

        response = await superuser_client.put(
            f"/api/v1/items/{item.id}",
            json={"title": "Admin override"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Admin override"


# ── DELETE ──────────────────────────────────────────────────────────


class TestDeleteItem:
    @pytest.mark.asyncio
    async def test_success(
        self, client: AsyncClient, mock_session: AsyncMock, user_id
    ):
        item = Item(
            id=uuid.uuid4(),
            title="To delete",
            status=ItemStatus.draft,
            owner_id=user_id,
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=item)
        )

        response = await client.delete(f"/api/v1/items/{item.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Item deleted successfully"
        mock_session.delete.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient, mock_session: AsyncMock):
        mock_session.execute = AsyncMock(return_value=_mock_execute_result())

        response = await client.delete(f"/api/v1/items/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_owner_returns_403(
        self, client: AsyncClient, mock_session: AsyncMock, other_user_id
    ):
        item = Item(
            id=uuid.uuid4(),
            title="Not mine",
            status=ItemStatus.draft,
            owner_id=other_user_id,
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=item)
        )

        response = await client.delete(f"/api/v1/items/{item.id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_superuser_can_delete_any(
        self,
        superuser_client: AsyncClient,
        mock_session: AsyncMock,
        other_user_id,
    ):
        item = Item(
            id=uuid.uuid4(),
            title="Other's",
            status=ItemStatus.draft,
            owner_id=other_user_id,
        )
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(item=item)
        )

        response = await superuser_client.delete(f"/api/v1/items/{item.id}")
        assert response.status_code == 200


# ── CACHE HITS ─────────────────────────────────────────────────────


class TestCacheHits:
    @pytest.mark.asyncio
    async def test_get_items_returns_cached_data(
        self, client: AsyncClient, monkeypatch
    ):
        """When cache_get returns data, the endpoint should return it directly."""
        cached_data = [
            {"id": str(uuid.uuid4()), "title": "Cached", "status": "draft",
             "description": None, "category": None,
             "owner_id": str(uuid.uuid4()), "created_at": None}
        ]
        monkeypatch.setattr(
            "app.api.routes.items.cache_get", AsyncMock(return_value=cached_data)
        )

        response = await client.get("/api/v1/items/")
        assert response.status_code == 200
        assert response.json() == cached_data

    @pytest.mark.asyncio
    async def test_get_item_returns_cached_data(
        self, client: AsyncClient, monkeypatch, user_id
    ):
        """When cache_get returns data for a single item, the endpoint uses it."""
        item_id = uuid.uuid4()
        cached_data = {
            "id": str(item_id), "title": "Cached Detail", "status": "draft",
            "description": None, "category": None,
            "owner_id": str(user_id), "created_at": None,
        }
        monkeypatch.setattr(
            "app.api.routes.items.cache_get", AsyncMock(return_value=cached_data)
        )

        response = await client.get(f"/api/v1/items/{item_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Cached Detail"

    @pytest.mark.asyncio
    async def test_category_density_returns_cached_data(
        self, client: AsyncClient, monkeypatch
    ):
        """When cache_get returns density data, the endpoint uses it."""
        cached_data = {
            "success": True,
            "data": {
                "total_items": 5,
                "categories": [
                    {"category": "electronics", "count": 3, "percentage": 60.0},
                    {"category": "books", "count": 2, "percentage": 40.0},
                ],
            },
        }
        monkeypatch.setattr(
            "app.api.routes.items.cache_get", AsyncMock(return_value=cached_data)
        )

        response = await client.get("/api/v1/items/analytics/category-density")
        assert response.status_code == 200
        assert response.json() == cached_data


# ── CATEGORY DENSITY ───────────────────────────────────────────────


class TestCategoryDensity:
    @pytest.mark.asyncio
    async def test_returns_density_data(
        self, client: AsyncClient, mock_session: AsyncMock
    ):
        rows = [
            SimpleNamespace(category=ItemCategory.electronics, count=3),
            SimpleNamespace(category=ItemCategory.books, count=2),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=result_mock)

        response = await client.get("/api/v1/items/analytics/category-density")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_items"] == 5
        assert len(data["data"]["categories"]) == 2

    @pytest.mark.asyncio
    async def test_empty_items(
        self, client: AsyncClient, mock_session: AsyncMock
    ):
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        response = await client.get("/api/v1/items/analytics/category-density")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_items"] == 0


# ── FILTER PARAMS ──────────────────────────────────────────────────


class TestGetItemsFilters:
    @pytest.mark.asyncio
    async def test_filter_by_status(
        self, client: AsyncClient, mock_session: AsyncMock, user_id
    ):
        items = [
            Item(
                id=uuid.uuid4(), title="Draft", status=ItemStatus.draft,
                owner_id=user_id,
            )
        ]
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(items=items)
        )

        response = await client.get("/api/v1/items/?status=draft")
        assert response.status_code == 200
        assert len(response.json()) == 1

    @pytest.mark.asyncio
    async def test_filter_by_category(
        self, client: AsyncClient, mock_session: AsyncMock, user_id
    ):
        items = [
            Item(
                id=uuid.uuid4(), title="Book", status=ItemStatus.draft,
                category=ItemCategory.books, owner_id=user_id,
            )
        ]
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(items=items)
        )

        response = await client.get("/api/v1/items/?category=books")
        assert response.status_code == 200
        assert len(response.json()) == 1

    @pytest.mark.asyncio
    async def test_superuser_sees_all_items(
        self, superuser_client: AsyncClient, mock_session: AsyncMock, user_id
    ):
        items = [
            Item(
                id=uuid.uuid4(), title=f"Item {i}", status=ItemStatus.draft,
                owner_id=user_id,
            )
            for i in range(5)
        ]
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(items=items)
        )

        response = await superuser_client.get("/api/v1/items/")
        assert response.status_code == 200
        assert len(response.json()) == 5
