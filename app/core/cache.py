import json
import logging
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None


async def init_redis() -> None:
    """Initialise the shared async Redis connection pool."""
    global _redis
    _redis = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True,
    )
    # Verify connection
    await _redis.ping()
    logger.info("Redis connection established")


async def close_redis() -> None:
    """Gracefully close the Redis connection pool."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


def get_redis() -> redis.Redis:
    """Return the current Redis client (for use as a FastAPI dependency)."""
    if _redis is None:
        raise RuntimeError("Redis is not initialised. Call init_redis() first.")
    return _redis


async def cache_get(key: str) -> Any | None:
    """Retrieve a cached JSON value by key. Returns None on miss."""
    try:
        data = await get_redis().get(key)
        if data is not None:
            return json.loads(data)
    except Exception:
        logger.warning("Redis GET failed for key=%s", key, exc_info=True)
    return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    """Store a JSON-serialisable value in the cache."""
    try:
        ttl = ttl or settings.REDIS_CACHE_TTL
        await get_redis().set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.warning("Redis SET failed for key=%s", key, exc_info=True)


async def cache_delete(key: str) -> None:
    """Delete a single key from the cache."""
    try:
        await get_redis().delete(key)
    except Exception:
        logger.warning("Redis DELETE failed for key=%s", key, exc_info=True)


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern (e.g. 'items:*')."""
    try:
        r = get_redis()
        cursor = None
        while cursor != 0:
            cursor, keys = await r.scan(cursor=cursor or 0, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
    except Exception:
        logger.warning("Redis DELETE pattern failed for pattern=%s", pattern, exc_info=True)
