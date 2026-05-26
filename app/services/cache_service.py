import time
import typing
from typing import Any, Optional, Tuple

from app.core.cache.redis_client import get_redis


class CacheService:
    @staticmethod
    async def store_session_context(session_id: str, context_data: dict) -> typing.Any:
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("session", session_id)
        await redis.set_json(key, context_data, ttl=3600)

    @staticmethod
    async def get_session_context(session_id: str) -> Optional[dict]:
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("session", session_id)
        return await redis.get_json(key)

    @staticmethod
    async def clear_session_context(session_id: str) -> typing.Any:
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("session", session_id)
        await redis.delete(key)

    @staticmethod
    async def store_task_status(task_id: str, status_data: dict) -> typing.Any:
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("task", task_id)
        await redis.set_json(key, status_data, ttl=86400)

    @staticmethod
    async def get_task_status(task_id: str) -> Optional[dict]:
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("task", task_id)
        return await redis.get_json(key)

    @staticmethod
    async def update_task_status(task_id: str, status_data: dict) -> typing.Any:
        """
        Automatically generated docstring.
        """
        await CacheService.store_task_status(task_id, status_data)

    @staticmethod
    async def cache_user(user_id: str, user_data: dict):
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("user", user_id)
        await redis.set_json(key, user_data, ttl=300)

    @staticmethod
    async def get_user(user_id: str) -> Optional[dict]:
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("user", user_id)
        return await redis.get_json(key)

    @staticmethod
    async def invalidate_user(user_id: str):
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("user", user_id)
        await redis.delete(key)

    @staticmethod
    async def rate_limit_check(
        identifier: str, limit: int, window_seconds: int
    ) -> Tuple[bool, int]:
        """
        Automatically generated docstring.
        """
        redis = get_redis()
        key = redis.make_key("ratelimit", identifier)
        now = time.time()

        pipeline = redis.client.pipeline(transaction=True)
        # Add current request timestamp
        pipeline.zadd(key, {str(now): now})
        # Remove timestamps older than window
        pipeline.zremrangebyscore(key, 0, now - window_seconds)
        # Count requests in window
        pipeline.zcount(key, now - window_seconds, now)
        # Optional: update expiry of the key so it cleans up naturally
        pipeline.expire(key, window_seconds)

        results = await pipeline.execute()
        count = results[2]  # The result of zcount

        allowed = count <= limit
        remaining = max(0, limit - count)

        return allowed, remaining
