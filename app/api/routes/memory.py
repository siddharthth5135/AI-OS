import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.chat import Chat
from app.db.models.user import User
from app.api.dependencies.auth import get_current_active_user
from app.services.memory.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])

class StoreMemoryPayload(BaseModel):
    content: str = Field(..., description="The factual content to store in long term memory")
    memory_type: str = Field("fact", description="The memory categorization type")
    importance: float = Field(0.5, description="Factual importance rating from 0.0 to 1.0")

@router.get("/history")
async def get_history(
    session_id: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve recent chat history from the database, filtered optionally by session_id.
    """
    stmt = select(Chat).where(Chat.user_id == current_user.id)
    if session_id:
        stmt = stmt.where(Chat.conversation_id == session_id)
    stmt = stmt.order_by(Chat.created_at.desc()).limit(limit)
    
    res = await db.execute(stmt)
    chats = res.scalars().all()
    
    # Return in chronological order
    ordered_chats = chats[::-1]
    
    return {
        "success": True,
        "data": [
            {
                "id": str(chat.id),
                "conversation_id": chat.conversation_id,
                "role": chat.role,
                "content": chat.content,
                "agent_type": chat.agent_type,
                "tokens_used": chat.tokens_used,
                "latency_ms": chat.latency_ms,
                "created_at": chat.created_at.isoformat() if chat.created_at else None
            } for chat in ordered_chats
        ],
        "message": "Chat history retrieved successfully."
    }

@router.post("/store", status_code=status.HTTP_201_CREATED)
async def store_memory(
    payload: StoreMemoryPayload,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually generate, embed, and store a fact in long-term vector memory.
    """
    memory_service = MemoryService()
    try:
        entry = await memory_service.store_long_term(
            user_id=str(current_user.id),
            content=payload.content,
            memory_type=payload.memory_type,
            db=db,
            importance=payload.importance
        )
        return {
            "success": True,
            "data": {
                "id": str(entry.id),
                "content": entry.content,
                "summary": entry.summary,
                "embedding_id": entry.embedding_id,
                "memory_type": entry.memory_type,
                "importance_score": entry.importance_score,
                "created_at": entry.created_at.isoformat() if entry.created_at else None
            },
            "message": "Factual memory successfully generated, embedded, and stored in database + pgvector."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save long-term memory: {str(e)}"
        )

@router.get("/search")
async def search_memory(
    q: str,
    limit: int = 5,
    current_user: User = Depends(get_current_active_user)
):
    """
    Perform a vector semantic search over the user's long-term memories.
    """
    if not q or not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query 'q' cannot be empty."
        )
        
    memory_service = MemoryService()
    try:
        results = await memory_service.retrieve_relevant(
            query=q,
            user_id=str(current_user.id),
            limit=limit
        )
        return {
            "success": True,
            "data": results,
            "message": "Semantic memory search completed."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic memory search execution error: {str(e)}"
        )
