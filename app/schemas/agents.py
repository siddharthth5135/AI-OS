from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class AgentChatResponseData(BaseModel):
    """Factual response payload from agent execution."""

    task_id: str = Field(
        ..., description="Unique task UUID representing this execution"
    )
    response: str = Field(..., description="Text response from the routed agent")
    agent_used: str = Field(
        ..., description="The name of the agent that processed the query"
    )
    memory_used: bool = Field(
        False, description="Whether short/long term memory context was used"
    )
    documents_used: bool = Field(
        False, description="Whether relevant document context chunks were used"
    )
    tokens_used: int = Field(0, description="Total tokens consumed by this LLM request")
    latency_ms: int = Field(0, description="Total execution latency in milliseconds")
    sources: List[Dict[str, Any]] = Field(
        default=[], description="Source references used by the agent"
    )


class AgentChatResponse(BaseResponse[AgentChatResponseData]):
    """Standard API response wrapping AgentChatResponseData."""

    pass


class TaskResponseData(BaseModel):
    """Detailed metadata for a background orchestrator task."""

    task_id: str = Field(..., description="Unique task UUID")
    status: str = Field(
        ...,
        description="Current processing status (pending, processing, completed, failed)",
    )
    task_type: str = Field(..., description="Classification category of the task")
    input_data: Dict[str, Any] = Field(..., description="Original request parameters")
    result_data: Optional[Dict[str, Any]] = Field(
        None, description="Final structured outcome payload"
    )
    error_message: Optional[str] = Field(
        None, description="Detailed error description if execution failed"
    )
    agent_used: Optional[str] = Field(
        None, description="Name of agent that resolved the task"
    )
    tokens_used: int = Field(0, description="Tokens consumed")
    processing_time_ms: Optional[int] = Field(
        None, description="Task execution latency in milliseconds"
    )
    started_at: Optional[str] = Field(
        None, description="ISO timestamp representing task start time"
    )
    completed_at: Optional[str] = Field(
        None, description="ISO timestamp representing task completion time"
    )


class TaskResponse(BaseResponse[TaskResponseData]):
    """Standard API response wrapping TaskResponseData."""

    pass


class CodeResponseData(BaseModel):
    """Outcome payload from the Code Agent execution."""

    task_id: str = Field(..., description="Unique task UUID")
    response: str = Field(..., description="Generated code or explanation text")
    agent_used: str = Field("code", description="The routed agent name")
    memory_used: bool = Field(default=False)
    documents_used: bool = Field(default=False)
    tokens_used: int = Field(0, description="Tokens consumed")
    latency_ms: int = Field(0, description="Execution latency")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Code execution or parsing metadata details"
    )


class CodeResponse(BaseResponse[CodeResponseData]):
    """Standard API response wrapping CodeResponseData."""

    pass
