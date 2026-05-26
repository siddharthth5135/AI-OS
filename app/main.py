import typing

"""
AI OS - Multi-Agent AI Operating System
Main FastAPI application entry point
"""

import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict

import redis.asyncio as redis
import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config.settings import settings
from app.core.logging.logger import get_logger, setup_logging
from app.core.middleware.logging_middleware import LoggingMiddleware

# Initialize logging immediately
setup_logging(debug=settings.debug)
logger = get_logger("ai_os.main")

# Global variables managed elsewhere


def handle_shutdown_signal(signum, frame) -> typing.Any:
    """Handle SIGTERM and SIGINT for graceful shutdown."""
    logger.info("received_shutdown_signal", signum=signum)
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown_signal)
signal.signal(signal.SIGINT, handle_shutdown_signal)


@asynccontextmanager
async def lifespan(app: FastAPI) -> typing.Any:
    """
    Automatically generated docstring.
    """
    import time

    from app.core.cache.redis_client import get_redis
    from app.services.embeddings.embedding_service import get_embedding_service
    from app.services.llm.gemini_client import get_llm_client
    from app.services.orchestration.orchestrator import AgentOrchestrator
    from app.vectorstore.pgvector_service import \
        get_pgvector_service as get_pgvector

    setup_logging(settings.debug)
    logger = get_logger("startup")
    logger.info("starting", version=settings.version, debug=settings.debug)
    _start_time = time.time()

    for name, coro in [
        ("redis", get_redis().connect(settings.redis_url.get_secret_value())),
        ("pgvector", get_pgvector().initialize()),
        ("embeddings", get_embedding_service().initialize()),
        ("llm", get_llm_client().initialize()),
    ]:
        try:
            await coro
            logger.info(f"{name}_ready")
        except Exception as e:
            logger.error(f"{name}_failed", error=str(e))
            if name in ("redis",):  # Critical services
                raise  # Stop startup

    orch = AgentOrchestrator()
    await orch.initialize()
    app.state.orchestrator = orch
    app.state.start_time = time.time()
    logger.info("startup_complete", agents=list(orch._agents.keys()))

    yield  # App runs

    await get_redis().disconnect()
    logger.info("shutdown_complete")


# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    summary="Multi-Agent AI Operating System",
    description="A production-grade Multi-Agent AI Operating System with LLM integration, "
    "vector storage, and intelligent agent orchestration.",
    lifespan=lifespan,
    # Standard documentation URLs
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Add Middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.exceptions import RequestValidationError


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> typing.Any:
    """
    Global exception handler for HTTPException.
    Follows Rule 8: {"success": false, "error": "..."}
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> typing.Any:
    """
    Global exception handler for RequestValidationError.
    Follows Rule 8 format.
    """
    errors = exc.errors()
    error_msgs = []
    for error in errors:
        loc = ".".join([str(l) for l in error.get("loc", [])])
        msg = error.get("msg", "")
        error_msgs.append(f"{loc}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "; ".join(error_msgs) if error_msgs else "Validation error",
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> typing.Any:
    """
    Global exception handler for unhandled exceptions.
    """
    logger.error("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )


@app.get("/", tags=["system"])
async def root() -> Dict[str, Any]:
    """
    Root endpoint returning project information.
    Following the mandatory response format: {"success":true,"data":{},"message":"..."}
    """
    return {
        "success": True,
        "data": {
            "name": settings.app_name,
            "version": settings.version,
            "description": "Multi-Agent AI Operating System",
        },
        "message": "Welcome to AI OS",
    }


from app.api.routes.agents import router as agents_router
# Include API routes
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.llm import router as llm_router
from app.api.routes.memory import router as memory_router
from app.api.routes.observability import router as obs_router
from app.api.websocket.chat_ws import ws_router

app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(agents_router, prefix=settings.api_v1_prefix)
app.include_router(documents_router, prefix=settings.api_v1_prefix)
app.include_router(memory_router, prefix=settings.api_v1_prefix)
app.include_router(llm_router, prefix=settings.api_v1_prefix)
app.include_router(obs_router)  # /health, /metrics at root
app.include_router(ws_router)  # /ws/chat at root
