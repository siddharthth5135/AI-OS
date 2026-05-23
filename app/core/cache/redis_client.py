import json
import redis.asyncio as aioredis
from typing import Optional, Any

class RedisClient:
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None

    async def connect(self, url: str, max_connections: int = 20):
        pool = aioredis.ConnectionPool.from_url(
            url, 
            decode_responses=True, 
            max_connections=max_connections
        )
        self.client = aioredis.Redis(connection_pool=pool)

    async def disconnect(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def ping(self) -> bool:
        if not self.client:
            return False
        return await self.client.ping()

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int = None):
        await self.client.set(key, value, ex=ttl)

    async def delete(self, key: str):
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        return await self.client.exists(key) > 0

    async def expire(self, key: str, ttl: int):
        await self.client.expire(key, ttl)

    async def incr(self, key: str) -> int:
        return await self.client.incr(key)

    async def incrby(self, key: str, amount: int) -> int:
        return await self.client.incrby(key, amount)

    async def get_json(self, key: str) -> Optional[Any]:
        val = await self.get(key)
        return json.loads(val) if val else None

    async def set_json(self, key: str, value: Any, ttl: int = None):
        await self.set(key, json.dumps(value), ttl)

    async def publish(self, channel: str, message: str):
        await self.client.publish(channel, message)

    async def keys(self, pattern: str) -> list[str]:
        return await self.client.keys(pattern)

    async def zadd(self, key: str, mapping: dict):
        await self.client.zadd(key, mapping)

    async def zrangebyscore(self, key: str, min: float, max: float):
        return await self.client.zrangebyscore(key, min, max)

    async def zremrangebyscore(self, key: str, min: float, max: float):
        await self.client.zremrangebyscore(key, min, max)

    async def zcount(self, key: str, min: float, max: float) -> int:
        return await self.client.zcount(key, min, max)

    def make_key(self, namespace: str, *parts) -> str:
        parts_str = ":".join(str(p) for p in parts)
        return f"ai_os:{namespace}:{parts_str}" if parts_str else f"ai_os:{namespace}"

_redis_client = RedisClient()

def get_redis() -> RedisClient:
    return _redis_client
