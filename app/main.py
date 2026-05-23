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
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config.settings import settings
from app.core.logging.logger import setup_logging, get_logger
from app.core.middleware.logging_middleware import LoggingMiddleware

# Initialize logging immediately
setup_logging(debug=settings.debug)
logger = get_logger("ai_os.main")

# Global variables managed elsewhere


def handle_shutdown_signal(signum, frame):
    """Handle SIGTERM and SIGINT for graceful shutdown."""
    logger.info("received_shutdown_signal", signum=signum)
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown_signal)
signal.signal(signal.SIGINT, handle_shutdown_signal)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async lifespan context manager for application startup and shutdown.
    - Connects to Redis
    - Logs startup summary
    """
    from app.core.cache.redis_client import get_redis
    
    # Startup Summary (Log everything except secrets)
    logger.info("startup.summary",
                app_name=settings.app_name,
                version=settings.version,
                debug=settings.debug,
                api_prefix=settings.api_v1_prefix,
                environment="development" if settings.debug else "production")

    # Connect to Redis
    try:
        await get_redis().connect(settings.redis_url.get_secret_value())
        await get_redis().ping()
        logger.info("startup.redis_connected")
    except Exception as e:
        logger.error("startup.redis_failed", error=str(e))
        
    # Connect to LLM
    try:
        from app.services.llm.gemini_client import get_llm_client
        await get_llm_client().initialize()
        healthy = await get_llm_client().health_check()
        logger.info("llm_ready", healthy=healthy)
    except Exception as e:
        logger.error("llm_init_failed", error=str(e))
    
    # Initialize Vector Storage and Embedding Services
    try:
        from app.vectorstore.pgvector_service import get_pgvector_service
        from app.services.embeddings.embedding_service import get_embedding_service
        
        await get_embedding_service().initialize()
        await get_pgvector_service().initialize()
        logger.info("vector_and_embedding_services_ready")
    except Exception as e:
        logger.error("vector_and_embedding_services_init_failed", error=str(e))
    
    # Initialize Agent Orchestrator
    try:
        from app.services.orchestration.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        await orch.initialize()
        app.state.orchestrator = orch
        logger.info("orchestrator_ready")
    except Exception as e:
        logger.error("orchestrator_init_failed", error=str(e))
    
    yield
    
    # Shutdown: Cleanup resources
    await get_redis().disconnect()
    logger.info("shutdown.redis_closed")
    
    logger.info("shutdown.complete")


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
    openapi_url="/openapi.json"
)

# Add Middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.exceptions import RequestValidationError

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Global exception handler for HTTPException.
    Follows Rule 8: {"success": false, "error": "..."}
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
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
            "error": "; ".join(error_msgs) if error_msgs else "Validation error"
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled exceptions.
    """
    logger.error("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error"
        },
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
        "message": "Welcome to AI OS"
    }


# Include API routes
from app.api.v1.api import api_router
from app.api.websocket.chat_ws import ws_router
from app.api.routes.observability import router as observability_router

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(ws_router)
app.include_router(observability_router)
