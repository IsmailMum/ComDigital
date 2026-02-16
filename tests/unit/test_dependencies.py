import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.dependencies import get_current_user, get_db
from app.core.exceptions import (
    CredentialsValidationError,
    UserNotFoundError,
    InactiveUserError,
)
from app.core.security import create_access_token
from app.models import User


# ── get_db ────────────────────────────────────────────────────────


class TestGetDb:
    @pytest.mark.asyncio
    async def test_yields_session(self):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()

        # async context manager that yields mock_session
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = cm

        with patch("app.api.dependencies.async_session", mock_session_maker):
            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session


# ── get_current_user ──────────────────────────────────────────────


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_active_user(self):
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="dep@example.com",
            hashed_password="fakehash",
            is_active=True,
        )
        token = create_access_token(str(user_id), expires_delta=timedelta(minutes=30))
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=user)

        result = await get_current_user(session=mock_session, token=token)
        assert result is user

    @pytest.mark.asyncio
    async def test_raises_credentials_error_on_invalid_token(self):
        mock_session = AsyncMock()

        with pytest.raises(CredentialsValidationError):
            await get_current_user(session=mock_session, token="invalid.token.here")

    @pytest.mark.asyncio
    async def test_raises_user_not_found_when_missing(self):
        user_id = uuid.uuid4()
        token = create_access_token(str(user_id), expires_delta=timedelta(minutes=30))
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundError):
            await get_current_user(session=mock_session, token=token)

    @pytest.mark.asyncio
    async def test_raises_inactive_user_error(self):
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="inactive@example.com",
            hashed_password="fakehash",
            is_active=False,
        )
        token = create_access_token(str(user_id), expires_delta=timedelta(minutes=30))
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=user)

        with pytest.raises(InactiveUserError):
            await get_current_user(session=mock_session, token=token)
