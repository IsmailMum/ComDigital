from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import FastAPI


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_calls_init_and_close_redis(self):
        mock_handler = MagicMock()
        mock_handler.start = AsyncMock()
        mock_handler.stop = AsyncMock()

        with patch("app.main.init_redis", new_callable=AsyncMock) as mock_init, \
             patch("app.main.close_redis", new_callable=AsyncMock) as mock_close, \
             patch("app.main.db_handler", mock_handler):
            from app.main import lifespan

            async with lifespan(FastAPI()):
                mock_init.assert_awaited_once()
                mock_handler.start.assert_awaited_once()
                mock_close.assert_not_awaited()

            mock_handler.stop.assert_awaited_once()
            mock_close.assert_awaited_once()
