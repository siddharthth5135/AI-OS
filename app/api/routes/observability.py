import asyncio
import time
import typing
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_admin
from app.core.cache.redis_client import get_redis
from app.core.config.settings import settings
from app.core.logging.logger import get_logger
from app.core.observability.metrics import get_metrics
from app.db.database import AsyncSessionLocal, get_db
from app.db.models.document import Document
from app.db.models.task import Task
from app.db.models.user import User
from app.schemas.base import ErrorResponse
from app.schemas.observability import AdminStatsResponse, HealthCheckResponse
from app.services.llm.gemini_client import get_llm_client
from app.services.streaming.connection_manager import connection_manager

_start_time = time.time()
router = APIRouter(tags=["Observability"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Check system health status",
    description="Validates integration connections (Postgres, Redis, PgVector, Gemini) and returns statuses. 200 for healthy, 207 for degraded (critical databases ok), and 503 for unhealthy.",
)
async def health_check() -> typing.Any:
    """
    Perform check on PostgreSQL, Redis, PgVector, and Gemini.
    """
    checks = await asyncio.gather(
        _check_supabase_db(),
        _check_upstash_redis(),
        _check_supabase_storage(),
        _check_gemini(),
        return_exceptions=True,
    )
    results = {
        "postgres": (
            checks[0]
            if not isinstance(checks[0], Exception)
            else {"ok": False, "error": str(checks[0])}
        ),
        "redis": (
            checks[1]
            if not isinstance(checks[1], Exception)
            else {"ok": False, "error": str(checks[1])}
        ),
        "pgvector": (
            checks[2]
            if not isinstance(checks[2], Exception)
            else {"ok": False, "error": str(checks[2])}
        ),
        "gemini": (
            checks[3]
            if not isinstance(checks[3], Exception)
            else {"ok": False, "error": str(checks[3])}
        ),
    }
    all_ok = all(r.get("ok") for r in results.values())
    critical_ok = results["postgres"]["ok"] and results["redis"]["ok"]

    if all_ok:
        status, code = "healthy", 200
    elif critical_ok:
        status, code = "degraded", 207
    else:
        status, code = "unhealthy", 503

    return JSONResponse(
        {
            "status": status,
            "services": results,
            "version": settings.version,
            "uptime_seconds": int(time.time() - _start_time),
        },
        status_code=code,
    )


async def _check_supabase_db() -> dict:
    try:
        start = time.time()
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
        return {"ok": True, "latency_ms": int((time.time() - start) * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


async def _check_upstash_redis() -> dict:
    try:
        start = time.time()
        await asyncio.wait_for(get_redis().ping(), timeout=2.0)
        return {"ok": True, "latency_ms": int((time.time() - start) * 1000)}
    except Exception:
        return {"ok": False}


async def _check_supabase_storage() -> dict:
    try:
        import httpx

        qdrant_url = f"http://{settings.pgvector_host}:{settings.pgvector_port}"
        async with httpx.AsyncClient() as client:
            res = await asyncio.wait_for(
                client.get(f"{qdrant_url}/collections", timeout=2.0), timeout=2.0
            )
            if res.status_code == 200:
                return {"ok": True}
        return {"ok": False}
    except Exception:
        return {"ok": False}


async def _check_gemini() -> dict:
    try:
        healthy = await asyncio.wait_for(get_llm_client().health_check(), timeout=2.0)
        return {"ok": healthy}
    except Exception:
        return {"ok": False}


logger = get_logger("ai_os.observability")


@router.get(
    "/metrics",
    summary="Get system Prometheus metrics",
    description="Exposes application-level metrics (request latencies, errors, WebSocket states) in standard Prometheus format. Rate-limited to 10 requests per minute.",
    responses={429: {"description": "Rate limit exceeded", "model": ErrorResponse}},
)
async def prometheus_metrics(request: Request) -> typing.Any:
    """
    Retrieve application metrics in Prometheus text format.
    """
    try:
        from app.services.cache_service import CacheService

        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = await CacheService.rate_limit_check(
            f"metrics:{client_ip}", limit=10, window_seconds=60
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for /metrics. Maximum 10 requests per minute.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("metrics.rate_limit_error", error=str(e))

    data, content_type = get_metrics()
    return Response(content=data, media_type=content_type)


@router.get(
    "/api/v1/admin/stats",
    response_model=AdminStatsResponse,
    dependencies=[Depends(require_admin)],
    summary="Get admin statistics",
    description="Gathers user counts, background task counts by status, active WS connections, token count, and file count. Restricted to admin role.",
    responses={
        401: {"description": "Not authenticated", "model": ErrorResponse},
        403: {
            "description": "Access forbidden: Requires admin privileges",
            "model": ErrorResponse,
        },
    },
)
async def admin_stats(db: AsyncSession = Depends(get_db)) -> typing.Any:
    """
    Aggregate statistics for administrative usage.
    """
    # 1. Total users
    res_users = await db.execute(select(func.count(User.id)))
    total_users = res_users.scalar() or 0

    # 2. Total tasks
    res_tasks = await db.execute(select(func.count(Task.id)))
    total_tasks = res_tasks.scalar() or 0

    # 3. Tasks by status
    res_status = await db.execute(
        select(Task.status, func.count(Task.id)).group_by(Task.status)
    )
    tasks_by_status = {status_name: count for status_name, count in res_status.all()}

    # 4. Active WS connections
    active_ws_connections = connection_manager.active_count()

    # 5. Total tokens today (from Redis)
    total_tokens_today = 0
    try:
        redis = get_redis()
        today_str = datetime.now(timezone.utc).date().isoformat()
        redis_key = f"stats:tokens:today:{today_str}"
        val = await redis.get(redis_key)
        total_tokens_today = int(val) if val else 0
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Ignored error in Exception: {e}")

    # 6. Total documents
    res_docs = await db.execute(select(func.count(Document.id)))
    total_documents = res_docs.scalar() or 0

    return {
        "success": True,
        "data": {
            "total_users": total_users,
            "total_tasks": total_tasks,
            "tasks_by_status": tasks_by_status,
            "active_ws_connections": active_ws_connections,
            "total_tokens_today": total_tokens_today,
            "total_documents": total_documents,
        },
        "message": "Admin statistics retrieved successfully",
    }
