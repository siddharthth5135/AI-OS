import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user
from app.db.database import get_db
from app.db.models.user import User
from app.db.models.task import Task
from app.services.orchestration.orchestrator import AgentOrchestrator, StreamEvent

router = APIRouter(prefix="/agents", tags=["agents"])

class ChatRequest(BaseModel):
    query: str
    session_id: str = "default"
    stream: bool = False
    doc_ids: Optional[List[str]] = []
    force_agent: Optional[str] = None

@router.post("/chat")
async def chat(
    request: Request,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    orchestrator: AgentOrchestrator = request.app.state.orchestrator
    
    # 1. Create a Task record in "pending"
    new_task = Task(
        user_id=current_user.id,
        task_type="orchestrated",
        status="pending",
        input_data={
            "query": payload.query,
            "session_id": payload.session_id,
            "doc_ids": payload.doc_ids,
            "force_agent": payload.force_agent
        },
        started_at=datetime.now(timezone.utc)
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    task_id = str(new_task.id)
 
    # 2. Process query
    if not payload.stream:
        # Non-streaming processing
        result = await orchestrator.process_task(
            query=payload.query,
            user_id=current_user.id,
            session_id=payload.session_id,
            task_id=task_id,
            context={"doc_ids": payload.doc_ids},
            force_agent=payload.force_agent
        )
        return {
            "success": True,
            "data": {
                "task_id": result.task_id,
                "response": result.response,
                "agent_used": result.agent_used,
                "memory_used": result.memory_used,
                "documents_used": result.documents_used,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
                "sources": result.sources
            },
            "message": "Task processed successfully"
        }
    else:
        # Streaming response
        async def event_generator():
            try:
                stream_gen = orchestrator.process_stream(
                    query=payload.query,
                    user_id=current_user.id,
                    session_id=payload.session_id,
                    task_id=task_id,
                    context={"doc_ids": payload.doc_ids},
                    force_agent=payload.force_agent
                )
                async for event in stream_gen:
                    yield f"event: {event.event}\ndata: {json.dumps(event.data)}\n\n"
            except Exception as e:
                yield f"event: task_failed\ndata: {json.dumps({'error': str(e)})}\n\n"
 
        return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/task/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task ID format."
        )

    stmt = select(Task).where(Task.id == task_uuid)
    res = await db.execute(stmt)
    task = res.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found."
        )

    # Verify ownership
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not own this task."
        )

    return {
        "success": True,
        "data": {
            "task_id": str(task.id),
            "status": task.status,
            "task_type": task.task_type,
            "input_data": task.input_data,
            "result_data": task.result_data,
            "error_message": task.error_message,
            "agent_used": task.agent_used,
            "tokens_used": task.tokens_used,
            "processing_time_ms": task.processing_time_ms,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        },
        "message": "Task status retrieved successfully"
    }

class ResearchRequest(BaseModel):
    query: str
    session_id: str = "default"
    doc_ids: Optional[List[str]] = []
    stream: bool = False

class CodeRequest(BaseModel):
    query: str
    code: Optional[str] = None
    language: Optional[str] = None
    stream: bool = False

@router.post("/research")
async def research(
    request: Request,
    payload: ResearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    orchestrator: AgentOrchestrator = request.app.state.orchestrator
    
    new_task = Task(
        user_id=current_user.id,
        task_type="research",
        status="pending",
        input_data={
            "query": payload.query,
            "session_id": payload.session_id,
            "doc_ids": payload.doc_ids
        },
        started_at=datetime.now(timezone.utc)
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    task_id = str(new_task.id)
    
    if not payload.stream:
        result = await orchestrator.process_task(
            query=payload.query,
            user_id=current_user.id,
            session_id=payload.session_id,
            task_id=task_id,
            context={"doc_ids": payload.doc_ids},
            force_agent="research"
        )
        return {
            "success": True,
            "data": {
                "task_id": result.task_id,
                "response": result.response,
                "agent_used": result.agent_used,
                "memory_used": result.memory_used,
                "documents_used": result.documents_used,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
                "sources": result.sources
            },
            "message": "Research task processed successfully"
        }
    else:
        async def event_generator():
            try:
                stream_gen = orchestrator.process_stream(
                    query=payload.query,
                    user_id=current_user.id,
                    session_id=payload.session_id,
                    task_id=task_id,
                    context={"doc_ids": payload.doc_ids},
                    force_agent="research"
                )
                async for event in stream_gen:
                    yield f"event: {event.event}\ndata: {json.dumps(event.data)}\n\n"
            except Exception as e:
                yield f"event: task_failed\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/code")
async def code(
    request: Request,
    payload: CodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    orchestrator: AgentOrchestrator = request.app.state.orchestrator
    
    new_task = Task(
        user_id=current_user.id,
        task_type="code",
        status="pending",
        input_data={
            "query": payload.query,
            "code": payload.code,
            "language": payload.language
        },
        started_at=datetime.now(timezone.utc)
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    task_id = str(new_task.id)
    
    if not payload.stream:
        result = await orchestrator.process_task(
            query=payload.query,
            user_id=current_user.id,
            session_id="default_code",
            task_id=task_id,
            force_agent="code",
            code=payload.code,
            language=payload.language
        )
        return {
            "success": True,
            "data": {
                "task_id": result.task_id,
                "response": result.response,
                "agent_used": result.agent_used,
                "memory_used": result.memory_used,
                "documents_used": result.documents_used,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
                "metadata": result.metadata
            },
            "message": "Code task processed successfully"
        }
    else:
        async def event_generator():
            try:
                stream_gen = orchestrator.process_stream(
                    query=payload.query,
                    user_id=current_user.id,
                    session_id="default_code",
                    task_id=task_id,
                    force_agent="code",
                    code=payload.code,
                    language=payload.language
                )
                async for event in stream_gen:
                    yield f"event: {event.event}\ndata: {json.dumps(event.data)}\n\n"
            except Exception as e:
                yield f"event: task_failed\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
