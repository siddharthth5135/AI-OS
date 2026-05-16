"""
AI OS - Multi-Agent AI Operating System
Main FastAPI application entry point
"""
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# Global shutdown flag
shutdown_event = False


def handle_shutdown_signal(signum, frame):
    """Handle SIGTERM and SIGINT for graceful shutdown."""
    global shutdown_event
    shutdown_event = True
    print(f"\n🛑 Received shutdown signal ({signum}). Shutting down gracefully...")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown_signal)
signal.signal(signal.SIGINT, handle_shutdown_signal)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async lifespan context manager for application startup and shutdown.
    Replaces deprecated @app.on_event decorators.
    """
    # Startup: Initialize connections and resources
    print("🚀 Starting up AI OS...")
    print("✅ Application startup complete")
    
    yield
    
    # Shutdown: Cleanup resources
    print("🛑 Shutting down AI OS...")
    print("✅ Cleanup complete")


# Initialize FastAPI application
app = FastAPI(
    title="AI OS",
    version="0.1.0",
    summary="Multi-Agent AI Operating System",
    description="A production-grade Multi-Agent AI Operating System with LLM integration, "
                "vector storage, and intelligent agent orchestration.",
    lifespan=lifespan,
)

# Configure CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "*")
if cors_origins == "*":
    origins = ["*"]
else:
    origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
