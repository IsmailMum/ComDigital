from unittest.mock import AsyncMock, patch

import pytest


class TestInitialData:
    @pytest.mark.asyncio
    async def test_main_calls_init_db(self):
        with patch("app.initial_data.init_db", new_callable=AsyncMock) as mock_init_db:
            from app.initial_data import main
            await main()

        mock_init_db.assert_awaited_once()
