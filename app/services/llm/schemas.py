from pydantic import BaseModel
from typing import Optional

class ChatMessage(BaseModel):
    role: str
    content: str

class LLMResponse(BaseModel):
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    model: str
    finish_reason: str

class LLMStreamChunk(BaseModel):
    text: str
    is_final: bool
    finish_reason: Optional[str] = None
    total_tokens: Optional[int] = None
