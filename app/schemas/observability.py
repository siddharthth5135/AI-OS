from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class ServiceStatus(BaseModel):
    """Integrity check response metadata for a dependency service."""

    ok: bool = Field(
        ..., description="True if the service is reachable and functioning"
    )
    latency_ms: Optional[int] = Field(
        None, description="Response latency in milliseconds, if applicable"
    )
    error: Optional[str] = Field(
        None, description="Description of service failure, if not healthy"
    )


class HealthCheckResponse(BaseModel):
    """Detailed health status report for the system gateway and dependencies."""

    status: str = Field(
        ..., description="System health category: healthy, degraded, or unhealthy"
    )
    services: Dict[str, ServiceStatus] = Field(
        ..., description="Breakdown of specific connected dependency services status"
    )
    version: str = Field(..., description="System version")
    uptime_seconds: int = Field(
        ..., description="Gateway server uptime since boot in seconds"
    )


class AdminStatsResponseData(BaseModel):
    """Operational metrics overview visible to admins."""

    total_users: int = Field(
        ..., description="Total user accounts registered in database"
    )
    total_tasks: int = Field(
        ..., description="Cumulative background orchestrator jobs processed"
    )
    tasks_by_status: Dict[str, int] = Field(
        ..., description="Orchestrated task counts grouped by status"
    )
    active_ws_connections: int = Field(
        ..., description="Total active WebSockets threads connected"
    )
    total_tokens_today: int = Field(
        ..., description="Sum of LLM tokens tracked today across all agents"
    )
    total_documents: int = Field(
        ..., description="Total file documents indexed in the vector store"
    )


class AdminStatsResponse(BaseResponse[AdminStatsResponseData]):
    """Standard API response wrapping AdminStatsResponseData."""

    pass
