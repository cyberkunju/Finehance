"""Redis cache configuration and utilities."""

import hashlib
import json
from functools import wraps
from typing import Any, Callable, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Redis cache manager for the application."""
    
    # Default TTLs in seconds
    DEFAULT_TTL = 300  # 5 minutes
    SHORT_TTL = 60  # 1 minute
    LONG_TTL = 3600  # 1 hour
    
    # Key prefixes for namespacing
    PREFIX = "ai_finance:"

    def __init__(self) -> None:
        """Initialize cache manager."""
        self.redis: Optional[Redis] = None
        self._stats = {"hits": 0, "misses": 0, "errors": 0}

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis = await aioredis.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self.redis.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e), exc_info=True)
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    def _make_key(self, key: str) -> str:
        """Create namespaced cache key."""
        return f"{self.PREFIX}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not self.redis:
            logger.warning("Redis not connected, skipping cache get")
            return None

        try:
            value = await self.redis.get(self._make_key(key))
            if value:
                self._stats["hits"] += 1
                return json.loads(value)
            self._stats["misses"] += 1
            return None
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Cache get error", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds (optional, defaults to DEFAULT_TTL)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            logger.warning("Redis not connected, skipping cache set")
            return False

        try:
            serialized = json.dumps(value, default=str)
            ttl = expire or self.DEFAULT_TTL
            await self.redis.setex(self._make_key(key), ttl, serialized)
            return True
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Cache set error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            logger.warning("Redis not connected, skipping cache delete")
            return False

        try:
            await self.redis.delete(self._make_key(key))
            return True
        except Exception as e:
            logger.error("Cache delete error", key=key, error=str(e))
            return False

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dict mapping keys to values (only found keys)
        """
        if not self.redis or not keys:
            return {}

        try:
            prefixed_keys = [self._make_key(k) for k in keys]
            values = await self.redis.mget(prefixed_keys)
            result = {}
            for key, value in zip(keys, values):
                if value:
                    result[key] = json.loads(value)
                    self._stats["hits"] += 1
                else:
                    self._stats["misses"] += 1
            return result
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Cache get_many error", error=str(e))
            return {}

    async def set_many(self, items: dict[str, Any], expire: Optional[int] = None) -> bool:
        """Set multiple values in cache.
        
        Args:
            items: Dict of key-value pairs
            expire: Expiration time in seconds
            
        Returns:
            True if successful
        """
        if not self.redis or not items:
            return False

        try:
            ttl = expire or self.DEFAULT_TTL
            pipe = self.redis.pipeline()
            for key, value in items.items():
                serialized = json.dumps(value, default=str)
                pipe.setex(self._make_key(key), ttl, serialized)
            await pipe.execute()
            return True
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Cache set_many error", error=str(e))
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern.
        
        Args:
            pattern: Key pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.redis:
            logger.warning("Redis not connected, skipping cache clear")
            return 0

        try:
            full_pattern = self._make_key(pattern)
            keys = []
            async for key in self.redis.scan_iter(match=full_pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info("Cleared cache keys", pattern=pattern, count=deleted)
                return deleted
            return 0
        except Exception as e:
            logger.error("Cache clear error", pattern=pattern, error=str(e))
            return 0

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        stats = self._stats.copy()
        total = stats["hits"] + stats["misses"]
        stats["hit_rate"] = (stats["hits"] / total * 100) if total > 0 else 0
        return stats


# Global cache manager instance
cache_manager = CacheManager()


def cached(
    key_prefix: str,
    expire: Optional[int] = None,
    key_builder: Optional[Callable[..., str]] = None
):
    """Decorator for caching async function results.
    
    Args:
        key_prefix: Prefix for the cache key
        expire: TTL in seconds
        key_builder: Optional function to build cache key from args
        
    Example:
        @cached("user", expire=300)
        async def get_user(user_id: int):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = f"{key_prefix}:{key_builder(*args, **kwargs)}"
            else:
                # Default: hash args and kwargs
                key_parts = [str(arg) for arg in args]
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                key_hash = hashlib.md5(":".join(key_parts).encode()).hexdigest()[:16]
                cache_key = f"{key_prefix}:{key_hash}"
            
            # Try cache first
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_manager.set(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator


async def get_cache() -> CacheManager:
    """Dependency for getting cache manager.
    
    Returns:
        CacheManager instance
    """
    return cache_manager
