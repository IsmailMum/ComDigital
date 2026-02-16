import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import cache


@pytest.fixture(autouse=True)
def _reset_redis_state():
    """Ensure each test starts with a clean _redis state."""
    original = cache._redis
    yield
    cache._redis = original


# ── init_redis / close_redis / get_redis ──────────────────────────


class TestInitRedis:
    @pytest.mark.asyncio
    async def test_initialises_and_pings(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping = AsyncMock()

        with patch("app.core.cache.redis.Redis", return_value=mock_redis_instance):
            await cache.init_redis()

        assert cache._redis is mock_redis_instance
        mock_redis_instance.ping.assert_awaited_once()


class TestCloseRedis:
    @pytest.mark.asyncio
    async def test_closes_connection(self):
        mock_redis_instance = AsyncMock()
        cache._redis = mock_redis_instance

        await cache.close_redis()

        mock_redis_instance.aclose.assert_awaited_once()
        assert cache._redis is None

    @pytest.mark.asyncio
    async def test_noop_when_not_initialised(self):
        cache._redis = None
        await cache.close_redis()  # should not raise
        assert cache._redis is None


class TestGetRedis:
    def test_returns_client_when_initialised(self):
        mock_redis_instance = MagicMock()
        cache._redis = mock_redis_instance

        result = cache.get_redis()
        assert result is mock_redis_instance

    def test_raises_when_not_initialised(self):
        cache._redis = None
        with pytest.raises(RuntimeError, match="Redis is not initialised"):
            cache.get_redis()


# ── cache_get ─────────────────────────────────────────────────────


class TestCacheGet:
    @pytest.mark.asyncio
    async def test_returns_data_on_hit(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.get = AsyncMock(return_value=json.dumps({"key": "value"}))
        cache._redis = mock_redis_instance

        result = await cache.cache_get("test-key")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_returns_none_on_miss(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.get = AsyncMock(return_value=None)
        cache._redis = mock_redis_instance

        result = await cache.cache_get("missing-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.get = AsyncMock(side_effect=Exception("connection lost"))
        cache._redis = mock_redis_instance

        result = await cache.cache_get("error-key")
        assert result is None


# ── cache_set ─────────────────────────────────────────────────────


class TestCacheSet:
    @pytest.mark.asyncio
    async def test_stores_value(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.set = AsyncMock()
        cache._redis = mock_redis_instance

        await cache.cache_set("my-key", {"data": 123})
        mock_redis_instance.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.set = AsyncMock(side_effect=Exception("write fail"))
        cache._redis = mock_redis_instance

        await cache.cache_set("bad-key", "value")  # should not raise


# ── cache_delete ──────────────────────────────────────────────────


class TestCacheDelete:
    @pytest.mark.asyncio
    async def test_deletes_key(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.delete = AsyncMock()
        cache._redis = mock_redis_instance

        await cache.cache_delete("del-key")
        mock_redis_instance.delete.assert_awaited_once_with("del-key")

    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.delete = AsyncMock(side_effect=Exception("fail"))
        cache._redis = mock_redis_instance

        await cache.cache_delete("bad-key")  # should not raise


# ── cache_delete_pattern ──────────────────────────────────────────


class TestCacheDeletePattern:
    @pytest.mark.asyncio
    async def test_scans_and_deletes_matching_keys(self):
        mock_redis_instance = AsyncMock()
        # Simulate one scan iteration: returns cursor=0 (done) with two keys
        mock_redis_instance.scan = AsyncMock(return_value=(0, ["key:1", "key:2"]))
        mock_redis_instance.delete = AsyncMock()
        cache._redis = mock_redis_instance

        await cache.cache_delete_pattern("key:*")

        mock_redis_instance.scan.assert_awaited_once()
        mock_redis_instance.delete.assert_awaited_once_with("key:1", "key:2")

    @pytest.mark.asyncio
    async def test_handles_no_matching_keys(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.scan = AsyncMock(return_value=(0, []))
        mock_redis_instance.delete = AsyncMock()
        cache._redis = mock_redis_instance

        await cache.cache_delete_pattern("nothing:*")

        mock_redis_instance.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        mock_redis_instance = AsyncMock()
        mock_redis_instance.scan = AsyncMock(side_effect=Exception("scan fail"))
        cache._redis = mock_redis_instance

        await cache.cache_delete_pattern("bad:*")  # should not raise
