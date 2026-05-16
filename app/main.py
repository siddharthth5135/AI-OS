"""
AI OS - Multi-Agent AI Operating System
Main FastAPI application entry point
"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async lifespan context manager for application startup and shutdown.
    Replaces deprecated @app.on_event decorators.
    """
    # Startup: Initialize connections and resources
    print("🚀 Starting up AI OS...")
    # TODO: Initialize database connection pool
    # TODO: Initialize Redis connection
    # TODO: Initialize LLM clients (Google Gemini)
    # TODO: Initialize vector store
    # TODO: Initialize Celery workers
    
    yield
    
    # Shutdown: Cleanup resources
    print("🛑 Shutting down AI OS...")
    # TODO: Close database connections
    # TODO: Close Redis connections
    # TODO: Cleanup LLM client resources
    # TODO: Close vector store connections


# Initialize FastAPI application
app = FastAPI(
    title="AI OS",
    version="0.1.0",
    summary="Multi-Agent AI Operating System",
    description="A production-grade Multi-Agent AI Operating System with LLM integration, "
                "vector storage, and intelligent agent orchestration.",
    lifespan=lifespan,
)

# Configure CORS middleware for development
# NOTE: In production, replace ["*"] with specific allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


@app.get("/")
async def root():
    """
    Root endpoint returning project information.
    
    Returns:
        dict: Project metadata including name, version, description, and docs URL
    """
    return {
        "name": "AI OS",
        "version": "0.1.0",
        "description": "Multi-Agent AI Operating System",
        "docs_url": "/docs"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and orchestration tools.
    
    Returns:
        dict: Health status with version and ISO8601 timestamp
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
