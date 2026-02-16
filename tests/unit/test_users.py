import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models import User, UserCreate


# ── REGISTER ────────────────────────────────────────────────────────


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, mock_session: AsyncMock):
        # get_user_by_email will call session.execute() → .scalars().first()
        # Return None to indicate no existing user
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )

        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "newuser@example.com",
                "password": "strongpass123",
                "full_name": "New User",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email_via_lookup(
        self, client: AsyncClient, mock_session: AsyncMock, test_user
    ):
        """If get_user_by_email finds an existing user, return 400."""
        # Make crud.get_user_by_email return an existing user
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=test_user)))
            )
        )

        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "testuser@example.com",
                "password": "strongpass123",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "USER_ALREADY_EXISTS"
        assert "already exists" in data["message"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email_via_integrity_error(
        self, client: AsyncClient, mock_session: AsyncMock
    ):
        """If IntegrityError occurs during create, return 400."""
        from sqlalchemy.exc import IntegrityError

        # get_user_by_email returns None (no user found in first check)
        # but create_user raises IntegrityError (race condition)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )
        mock_session.commit = AsyncMock(
            side_effect=IntegrityError("dupe", {}, None)
        )

        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "race@example.com",
                "password": "strongpass123",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "USER_ALREADY_EXISTS"
        assert "already exists" in data["message"]


# ── LOGIN ───────────────────────────────────────────────────────────


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, mock_session: AsyncMock):
        from app.core.security import get_password_hash

        password = "correctpassword"
        user = User(
            id=uuid.uuid4(),
            email="login@example.com",
            hashed_password=get_password_hash(password),
            is_active=True,
        )
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user)))
            )
        )

        response = await client.post(
            "/api/v1/users/login",
            data={"username": "login@example.com", "password": password},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, mock_session: AsyncMock):
        from app.core.security import get_password_hash

        user = User(
            id=uuid.uuid4(),
            email="login@example.com",
            hashed_password=get_password_hash("correctpassword"),
            is_active=True,
        )
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user)))
            )
        )

        response = await client.post(
            "/api/v1/users/login",
            data={"username": "login@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "INVALID_CREDENTIALS"
        assert "Incorrect email or password" in data["message"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient, mock_session: AsyncMock):
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )

        response = await client.post(
            "/api/v1/users/login",
            data={"username": "ghost@example.com", "password": "whatever"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, mock_session: AsyncMock):
        from app.core.security import get_password_hash

        password = "correctpassword"
        user = User(
            id=uuid.uuid4(),
            email="inactive@example.com",
            hashed_password=get_password_hash(password),
            is_active=False,
        )
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user)))
            )
        )

        response = await client.post(
            "/api/v1/users/login",
            data={"username": "inactive@example.com", "password": password},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "INACTIVE_USER"
        assert "Inactive user" in data["message"]


# ── PROFILE ─────────────────────────────────────────────────────────


class TestProfile:
    @pytest.mark.asyncio
    async def test_get_profile(self, client: AsyncClient):
        response = await client.get("/api/v1/users/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "testuser@example.com"
        assert data["full_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_update_profile(self, client: AsyncClient, mock_session: AsyncMock):
        response = await client.patch(
            "/api/v1/users/profile",
            json={"full_name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        mock_session.commit.assert_awaited_once()
