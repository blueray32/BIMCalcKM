"""Redis cache utilities for BIMCalc."""

import os
import pickle
from typing import Any

import redis.asyncio as redis


# Global Redis client (lazy initialized)
_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get Redis client instance (singleton).

    Returns:
        Async Redis client
    """
    global _redis_client

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

        _redis_client = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=False,  # We'll handle pickle serialization
        )

    return _redis_client


async def get_cached(key: str) -> Any | None:
    """Get value from Redis cache.

    Args:
        key: Cache key

    Returns:
        Cached value (unpickled) or None if not found/expired
    """
    client = await get_redis()

    try:
        cached_bytes = await client.get(key)
        if cached_bytes:
            return pickle.loads(cached_bytes)
    except Exception as e:
        # Log error but don't fail - cache misses are acceptable
        print(f"Redis get error for key {key}: {e}")

    return None


async def set_cached(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Set value in Redis cache.

    Args:
        key: Cache key
        value: Value to cache (will be pickled)
        ttl_seconds: Time to live in seconds (default 5 minutes)

    Returns:
        True if successful, False otherwise
    """
    client = await get_redis()

    try:
        value_bytes = pickle.dumps(value)
        await client.setex(key, ttl_seconds, value_bytes)
        return True
    except Exception as e:
        print(f"Redis set error for key {key}: {e}")
        return False


async def delete_cached(key: str) -> bool:
    """Delete key from Redis cache.

    Args:
        key: Cache key

    Returns:
        True if key was deleted, False otherwise
    """
    client = await get_redis()

    try:
        await client.delete(key)
        return True
    except Exception as e:
        print(f"Redis delete error for key {key}: {e}")
        return False


async def clear_cache_pattern(pattern: str) -> int:
    """Clear all keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "compliance:*")

    Returns:
        Number of keys deleted
    """
    client = await get_redis()

    try:
        keys = await client.keys(pattern)
        if keys:
            return await client.delete(*keys)
    except Exception as e:
        print(f"Redis clear pattern error for {pattern}: {e}")

    return 0
