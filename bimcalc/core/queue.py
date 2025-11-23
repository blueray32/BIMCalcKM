import os

from arq.connections import ArqRedis, RedisSettings, create_pool


def get_redis_settings() -> RedisSettings:
    """Get Redis settings from environment variables."""
    return RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://redis:6379")
    )

async def get_queue() -> ArqRedis:
    """Create a connection pool to the Redis queue."""
    return await create_pool(get_redis_settings())
