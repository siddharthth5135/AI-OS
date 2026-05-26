import json
import time
from typing import Optional

import google.api_core.exceptions
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.dependencies.auth import get_current_active_user
from app.core.config.settings import settings
from app.db.models.user import User
from app.schemas.base import ErrorResponse
from app.services.llm.gemini_client import get_llm_client
from app.services.llm.prompt_templates import (CODE_SYSTEM_PROMPT,
                                               DOCUMENT_SYSTEM_PROMPT,
                                               MEMORY_SYSTEM_PROMPT,
                                               RESEARCH_SYSTEM_PROMPT,
                                               WORKFLOW_SYSTEM_PROMPT)
from app.services.llm.schemas import LLMResponse
from app.services.llm.token_tracker import track_llm_usage

router = APIRouter(prefix="/llm", tags=["llm"])


class GenerateRequest(BaseModel):
    """Request payload for text generation."""

    prompt: str
    agent_type: str = "research"
    stream: bool = False
    temperature: float = 0.7


@router.post(
    "/generate",
    response_model=LLMResponse,
    summary="Generate raw text response",
    description="Sends prompt directly to Gemini LLM with chosen agent's system instructions. Supports SSE streaming when stream=true.",
    responses={
        400: {
            "description": "Prompt exceeds context window limit or invalid parameters",
            "model": ErrorResponse,
        },
        401: {"description": "Not authenticated", "model": ErrorResponse},
        503: {"description": "LLM service unavailable", "model": ErrorResponse},
    },
)
async def generate(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate text using Gemini LLM. Supports streaming.
    """
    llm = get_llm_client()

    agent_prompts = {
        "research": RESEARCH_SYSTEM_PROMPT,
        "code": CODE_SYSTEM_PROMPT,
        "document": DOCUMENT_SYSTEM_PROMPT,
        "workflow": WORKFLOW_SYSTEM_PROMPT,
        "memory": MEMORY_SYSTEM_PROMPT,
    }

    system_prompt = agent_prompts.get(request.agent_type, RESEARCH_SYSTEM_PROMPT)

    try:
        if not request.stream:
            response: LLMResponse = await llm.generate(
                request.prompt, system_prompt=system_prompt
            )
            background_tasks.add_task(
                track_llm_usage,
                str(current_user.id),
                request.agent_type,
                None,
                response,
            )
            return response

        async def event_generator():
            start_time = time.time()
            total_tokens = 0
            async for chunk in llm.generate_stream(
                request.prompt, system_prompt=system_prompt
            ):
                yield f"data: {json.dumps(chunk.model_dump())}\n\n"
                if chunk.is_final:
                    total_tokens = chunk.total_tokens or 0

            latency_ms = int((time.time() - start_time) * 1000)
            response_dummy = LLMResponse(
                text="",
                prompt_tokens=0,
                completion_tokens=total_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                model=settings.gemini_model,
                finish_reason="stop",
            )
            background_tasks.add_task(
                track_llm_usage,
                str(current_user.id),
                request.agent_type,
                None,
                response_dummy,
            )

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except google.api_core.exceptions.InvalidArgument as e:
        err_msg = str(e).lower()
        if (
            "context window" in err_msg
            or "token" in err_msg
            or "too long" in err_msg
            or "limit" in err_msg
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt exceeds maximum context window limits.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request parameters: {str(e)}",
        )
    except (
        google.api_core.exceptions.GoogleAPICallError,
        google.api_core.exceptions.ClientError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service unavailable due to API errors",
        )
    except Exception as e:
        # Check if it's an API key configuration error
        if "API_KEY" in str(e) or "API key" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service unavailable: Invalid API configuration",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {str(e)}",
        )
