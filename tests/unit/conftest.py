from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.dependencies import get_db, get_current_user


@pytest.fixture
def mock_session():
    """Fully-mocked AsyncSession — no database interaction."""
    session = AsyncMock()
    # `session.add()` is synchronous on a real AsyncSession, so use MagicMock
    # to avoid "coroutine was never awaited" warnings.
    session.add = MagicMock()
    return session


@pytest_asyncio.fixture
async def client(mock_session, test_user):
    """HTTP client authenticated as a regular user with a mocked DB session."""
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: test_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def superuser_client(mock_session, test_superuser):
    """HTTP client authenticated as a superuser with a mocked DB session."""
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: test_superuser
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
