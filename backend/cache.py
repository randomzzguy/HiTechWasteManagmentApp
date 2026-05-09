# =============================================================
# Hi-Tech Waste Management — Redis Cache Layer
# Provides caching utilities for frequently accessed data
# =============================================================

from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import redis.asyncio as redis
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T")


class RedisCache:
    """
    Async Redis cache wrapper with automatic connection management.
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            try:
                await self._client.ping()
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.error("Failed to connect to Redis: %s", e)
                self._client = None

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis cache disconnected")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._client:
            await self.connect()
            if not self._client:
                return None

        try:
            value = await self._client.get(key)
            if value is not None:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Cache get error for key %s: %s", key, e)
            return None

    async def set(
        self,
        key: str,
        value: Any,
        expire_seconds: int = 3600,
    ) -> bool:
        """Set value in cache with expiration."""
        if not self._client:
            await self.connect()
            if not self._client:
                return False

        try:
            await self._client.set(
                key,
                json.dumps(value),
                ex=expire_seconds,
            )
            return True
        except Exception as e:
            logger.error("Cache set error for key %s: %s", key, e)
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self._client:
            return False

        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error("Cache delete error for key %s: %s", key, e)
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self._client:
            return 0

        try:
            keys = await self._client.keys(pattern)
            if keys:
                await self._client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.error("Cache delete pattern error: %s", e)
            return 0

    async def clear(self) -> bool:
        """Clear all cache entries."""
        if not self._client:
            return False

        try:
            await self._client.flushdb()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error("Cache clear error: %s", e)
            return False


# Global cache instance
cache = RedisCache()


def cached(
    key_prefix: str,
    expire_seconds: int = 3600,
    key_builder: Optional[Callable] = None,
):
    """
    Decorator to cache function results in Redis.

    Args:
        key_prefix: Prefix for cache keys
        expire_seconds: Time-to-live in seconds (default: 1 hour)
        key_builder: Optional function to build custom cache key from args

    Usage:
        @cached("user_profile", expire_seconds=300)
        async def get_user(user_id: str):
            # Expensive database query
            return await db.get_user(user_id)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_prefix + ":" + key_builder(*args, **kwargs)
            else:
                # Simple key building from function args
                args_str = str(args) + str(sorted(kwargs.items()))
                import hashlib
                hash_key = hashlib.md5(args_str.encode()).hexdigest()
                cache_key = f"{key_prefix}:{hash_key}"

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug("Cache hit for key: %s", cache_key)
                return cached_value

            # Cache miss - call function
            logger.debug("Cache miss for key: %s", cache_key)
            result = await func(*args, **kwargs)

            # Store in cache
            await cache.set(cache_key, result, expire_seconds)

            return result

        return wrapper

    return decorator


async def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate all cache entries matching pattern."""
    return await cache.delete_pattern(pattern)


async def clear_all_cache() -> bool:
    """Clear all cache entries."""
    return await cache.clear()
