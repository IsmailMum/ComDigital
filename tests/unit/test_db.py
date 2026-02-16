from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User


class TestInitDb:
    @pytest.mark.asyncio
    async def test_creates_superuser_when_none_exists(self):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        # session.execute(...).scalars().first() returns None → no superuser
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker = MagicMock(return_value=cm)

        with patch("app.core.db.async_session", mock_session_maker), \
             patch("app.core.db.crud.create_user", new_callable=AsyncMock) as mock_create:
            from app.core.db import init_db
            await init_db()

        mock_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_superuser_exists(self):
        superuser = User(
            id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            email="admin@example.com",
            hashed_password="fakehash",
            is_superuser=True,
        )
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=superuser)))
            )
        )

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker = MagicMock(return_value=cm)

        with patch("app.core.db.async_session", mock_session_maker), \
             patch("app.core.db.crud.create_user", new_callable=AsyncMock) as mock_create:
            from app.core.db import init_db
            await init_db()

        mock_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_integrity_error_on_create(self):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker = MagicMock(return_value=cm)

        with patch("app.core.db.async_session", mock_session_maker), \
             patch(
                 "app.core.db.crud.create_user",
                 new_callable=AsyncMock,
                 side_effect=IntegrityError("dupe", {}, None),
             ):
            from app.core.db import init_db
            await init_db()  # should not raise

        mock_session.rollback.assert_awaited_once()
