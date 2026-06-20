"""Redis connection and caching utilities."""

from typing import Any, Optional

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = object  # type: ignore

from app.core.config import settings


class RedisClient:
    """Async Redis client wrapper (gracefully degrades if redis not installed)."""

    def __init__(self) -> None:
        self._client: Optional[Redis] = None
        self._available = REDIS_AVAILABLE

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if not self._available:
            return
        self._client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()

    @property
    def client(self) -> Redis:
        """Get Redis client instance."""
        if not self._available:
            raise RuntimeError("Redis not installed.")
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self._available:
            return None
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None,
    ) -> None:
        """Set key-value pair with optional expiration in seconds."""
        if not self._available:
            return
        await self.client.set(key, value, ex=expire)

    async def delete(self, key: str) -> None:
        """Delete a key."""
        if not self._available:
            return
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._available:
            return False
        return await self.client.exists(key) > 0

    async def expire(self, key: str, seconds: int) -> None:
        """Set expiration on a key."""
        if not self._available:
            return
        await self.client.expire(key, seconds)

    async def get_json(self, key: str) -> Optional[dict[str, Any]]:
        """Get JSON value by key."""
        if not self._available:
            return None
        import json
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(
        self,
        key: str,
        value: dict[str, Any],
        expire: Optional[int] = None,
    ) -> None:
        """Set JSON value with optional expiration."""
        if not self._available:
            return
        import json
        await self.set(key, json.dumps(value), expire=expire)

    async def incr(self, key: str) -> int:
        """Increment counter."""
        if not self._available:
            return 0
        return await self.client.incr(key)

    async def decr(self, key: str) -> int:
        """Decrement counter."""
        if not self._available:
            return 0
        return await self.client.decr(key)


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> Redis:
    """Dependency for getting Redis client."""
    return redis_client.client
