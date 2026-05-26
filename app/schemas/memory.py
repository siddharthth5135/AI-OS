from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class HistoryResponseItem(BaseModel):
    """Single chat conversation log entry."""

    id: str = Field(..., description="Unique chat message UUID")
    conversation_id: str = Field(
        ..., description="Active session or thread identification string"
    )
    role: str = Field(..., description="Author role (user or assistant)")
    content: str = Field(..., description="Raw text content of the message")
    agent_type: Optional[str] = Field(
        None, description="The agent routed to process this message, if applicable"
    )
    tokens_used: Optional[int] = Field(
        None, description="Tokens consumed during processing"
    )
    latency_ms: Optional[int] = Field(
        None, description="Response generation latency in milliseconds"
    )
    created_at: Optional[str] = Field(
        None, description="Message generation ISO 8601 timestamp"
    )


class HistoryResponse(BaseResponse[List[HistoryResponseItem]]):
    """Standard API response wrapping chat history entries."""

    pass


class MemoryStoreResponseData(BaseModel):
    """Saved fact metadata details returned after storing a long-term memory."""

    id: str = Field(..., description="Unique memory entry UUID")
    content: str = Field(..., description="Stored factual description")
    summary: Optional[str] = Field(None, description="Model-generated memory summary")
    embedding_id: Optional[str] = Field(
        None, description="Corresponding embedding identifier"
    )
    memory_type: str = Field("fact", description="Memory categorization type")
    importance_score: float = Field(
        0.5, description="Computed importance value between 0.0 and 1.0"
    )
    created_at: Optional[str] = Field(None, description="Creation ISO 8601 timestamp")


class MemoryStoreResponse(BaseResponse[MemoryStoreResponseData]):
    """Standard API response wrapping MemoryStoreResponseData."""

    pass


class MemorySearchResponseItem(BaseModel):
    """Individual factual memory search result matches."""

    id: str = Field(..., description="Source memory UUID")
    content: str = Field(..., description="Stored factual content matches")
    score: float = Field(..., description="Vector distance relevance score")
    payload: Dict[str, Any] = Field(
        default={}, description="Arbitrary metadata attributes"
    )


class MemorySearchResponse(BaseResponse[List[MemorySearchResponseItem]]):
    """Standard API response wrapping semantic memory search list."""

    pass
