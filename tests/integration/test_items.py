import pytest
from httpx import AsyncClient

from app.models import Item, ItemStatus, ItemCategory


# ── CRUD FLOW ───────────────────────────────────────────────────────


class TestItemCRUD:
    @pytest.mark.asyncio
    async def test_create_item(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/items/",
            json={
                "title": "Integration Item",
                "description": "Created in an integration test",
                "status": "draft",
                "category": "electronics",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Integration Item"
        assert data["status"] == "draft"
        assert data["category"] == "electronics"
        assert "id" in data
        assert "owner_id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_and_read_item(self, client: AsyncClient):
        # Create
        create_resp = await client.post(
            "/api/v1/items/",
            json={"title": "Read Me", "status": "published", "category": "books"},
        )
        item_id = create_resp.json()["id"]

        # Read
        get_resp = await client.get(f"/api/v1/items/{item_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Read Me"
        assert get_resp.json()["status"] == "published"

    @pytest.mark.asyncio
    async def test_update_item(self, client: AsyncClient):
        # Create
        resp = await client.post(
            "/api/v1/items/",
            json={"title": "Before Update", "category": "food"},
        )
        item_id = resp.json()["id"]

        # Update only title and status
        resp = await client.put(
            f"/api/v1/items/{item_id}",
            json={"title": "After Update", "status": "published"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "After Update"
        assert data["status"] == "published"
        assert data["category"] == "food"  # unchanged

    @pytest.mark.asyncio
    async def test_delete_item(self, client: AsyncClient):
        # Create
        resp = await client.post(
            "/api/v1/items/", json={"title": "To Delete"}
        )
        item_id = resp.json()["id"]

        # Delete
        resp = await client.delete(f"/api/v1/items/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Item deleted successfully"

        # Verify it's gone
        resp = await client.get(f"/api/v1/items/{item_id}")
        assert resp.status_code == 404


# ── LISTING & FILTERS ──────────────────────────────────────────────


class TestItemListing:
    @pytest.mark.asyncio
    async def test_list_items(self, client: AsyncClient):
        for i in range(3):
            await client.post("/api/v1/items/", json={"title": f"Item {i}"})

        resp = await client.get("/api/v1/items/")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_pagination(self, client: AsyncClient):
        for i in range(5):
            await client.post("/api/v1/items/", json={"title": f"Page {i}"})

        resp = await client.get("/api/v1/items/?skip=0&limit=2")
        assert len(resp.json()) == 2

        resp = await client.get("/api/v1/items/?skip=2&limit=2")
        assert len(resp.json()) == 2

        resp = await client.get("/api/v1/items/?skip=4&limit=2")
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_filter_by_status(self, client: AsyncClient):
        await client.post(
            "/api/v1/items/", json={"title": "Draft", "status": "draft"}
        )
        await client.post(
            "/api/v1/items/",
            json={"title": "Published", "status": "published"},
        )

        resp = await client.get("/api/v1/items/?status=draft")
        items = resp.json()
        assert all(i["status"] == "draft" for i in items)

    @pytest.mark.asyncio
    async def test_filter_by_category(self, client: AsyncClient):
        await client.post(
            "/api/v1/items/", json={"title": "Book", "category": "books"}
        )
        await client.post(
            "/api/v1/items/",
            json={"title": "Phone", "category": "electronics"},
        )

        resp = await client.get("/api/v1/items/?category=books")
        items = resp.json()
        assert len(items) == 1
        assert items[0]["category"] == "books"


# ── PERMISSIONS ─────────────────────────────────────────────────────


class TestItemPermissions:
    @pytest.mark.asyncio
    async def test_cannot_read_other_users_item(
        self, client: AsyncClient, db_session, registered_other_user
    ):
        item = Item(
            title="Not yours",
            status=ItemStatus.draft,
            owner_id=registered_other_user.id,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        resp = await client.get(f"/api/v1/items/{item.id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_cannot_update_other_users_item(
        self, client: AsyncClient, db_session, registered_other_user
    ):
        item = Item(
            title="Not yours",
            status=ItemStatus.draft,
            owner_id=registered_other_user.id,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        resp = await client.put(
            f"/api/v1/items/{item.id}", json={"title": "Stolen"}
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_cannot_delete_other_users_item(
        self, client: AsyncClient, db_session, registered_other_user
    ):
        item = Item(
            title="Not yours",
            status=ItemStatus.draft,
            owner_id=registered_other_user.id,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        resp = await client.delete(f"/api/v1/items/{item.id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_superuser_can_read_any_item(
        self, superuser_client: AsyncClient, db_session, user_id
    ):
        item = Item(
            title="Regular's item", status=ItemStatus.draft, owner_id=user_id
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        resp = await superuser_client.get(f"/api/v1/items/{item.id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_superuser_can_update_any_item(
        self, superuser_client: AsyncClient, db_session, user_id
    ):
        item = Item(
            title="Regular's item",
            status=ItemStatus.draft,
            category=ItemCategory.electronics,
            owner_id=user_id,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        resp = await superuser_client.put(
            f"/api/v1/items/{item.id}",
            json={"title": "Updated by admin"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated by admin"

    @pytest.mark.asyncio
    async def test_superuser_can_delete_any_item(
        self, superuser_client: AsyncClient, db_session, user_id
    ):
        item = Item(
            title="Regular's item", status=ItemStatus.draft, owner_id=user_id
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        resp = await superuser_client.delete(f"/api/v1/items/{item.id}")
        assert resp.status_code == 200


# ── ANALYTICS ───────────────────────────────────────────────────────


class TestCategoryDensity:
    @pytest.mark.asyncio
    async def test_category_density(self, client: AsyncClient):
        await client.post(
            "/api/v1/items/", json={"title": "A", "category": "electronics"}
        )
        await client.post(
            "/api/v1/items/", json={"title": "B", "category": "electronics"}
        )
        await client.post(
            "/api/v1/items/", json={"title": "C", "category": "books"}
        )

        resp = await client.get("/api/v1/items/analytics/category-density")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total_items"] == 3
