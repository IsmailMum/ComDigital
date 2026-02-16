import uuid
from unittest.mock import AsyncMock

import pytest

from app.models import User


# ── Disable Redis cache for all tests ────────────────────────────────


@pytest.fixture(autouse=True)
def _disable_cache(monkeypatch):
    """Replace Redis-backed cache helpers with no-ops so tests never need Redis."""
    monkeypatch.setattr(
        "app.api.routes.items.cache_get", AsyncMock(return_value=None)
    )
    monkeypatch.setattr("app.api.routes.items.cache_set", AsyncMock())
    monkeypatch.setattr(
        "app.api.routes.items.cache_delete_pattern", AsyncMock()
    )


# ── Reusable user fixtures ──────────────────────────────────────────


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def superuser_id() -> uuid.UUID:
    return uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
def test_user(user_id) -> User:
    return User(
        id=user_id,
        email="testuser@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        full_name="Test User",
    )


@pytest.fixture
def test_superuser(superuser_id) -> User:
    return User(
        id=superuser_id,
        email="admin@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=True,
        full_name="Admin User",
    )


@pytest.fixture
def other_user(other_user_id) -> User:
    return User(
        id=other_user_id,
        email="other@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        full_name="Other User",
    )
