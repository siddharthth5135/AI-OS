from datetime import datetime, timezone

from sqlalchemy import update

from app.core.cache.redis_client import get_redis
from app.db.models.task import Task
from app.db.session.database import AsyncSessionLocal
from app.services.llm.schemas import LLMResponse


async def track_llm_usage(
    user_id: str, agent_type: str, task_id: str, response: LLMResponse
):
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Update Redis
    token_key = redis.make_key("metrics", "tokens", user_id, today)
    latency_key = redis.make_key("metrics", "latency", agent_type)

    await redis.client.incrby(token_key, response.total_tokens)
    await redis.client.lpush(latency_key, response.latency_ms)
    # keep only last 100 latencies
    await redis.client.ltrim(latency_key, 0, 99)

    # Update DB Task
    if task_id:
        async with AsyncSessionLocal() as db:
            stmt = (
                update(Task)
                .where(Task.id == task_id)
                .values(
                    tokens_used=response.total_tokens,
                    processing_time_ms=response.latency_ms,
                    agent_used=agent_type,
                )
            )
            await db.execute(stmt)
            await db.commit()
