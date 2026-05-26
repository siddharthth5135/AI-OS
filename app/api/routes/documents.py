import os
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user
from app.core.config.settings import settings
from app.db.database import get_db
from app.db.models.document import Document
from app.db.models.user import User
from app.schemas.base import ErrorResponse
from app.schemas.documents import (DocumentDeleteResponse,
                                   DocumentDetailResponse,
                                   DocumentListResponse, DocumentQueryResponse,
                                   DocumentUploadResponse)
from app.services.documents.document_service import get_document_service
from app.vectorstore.pgvector_service import get_pgvector_service
from app.workers.document_worker import process_document

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


class QueryPayload(BaseModel):
    """Payload to query semantic document chunks."""

    query: str = Field(..., description="The search query text")
    doc_ids: Optional[List[str]] = Field(
        default=None, description="Optional document IDs to filter search scope"
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse document",
    description="Uploads document file (PDF, TXT, MD), validates size and magic bytes, creates DB entry, and queues Celery processing task.",
    responses={
        400: {"description": "Invalid file content structure", "model": ErrorResponse},
        413: {"description": "File exceeds size limits", "model": ErrorResponse},
        415: {"description": "Unsupported media format", "model": ErrorResponse},
        500: {"description": "Database operation failure", "model": ErrorResponse},
    },
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload document file (PDF, TXT, MD), validate sizes/magic bytes, and queue Celery processing.
    """
    # 1. Check file extension
    filename = file.filename or ""
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed types: {list(ALLOWED_EXTENSIONS)}",
        )

    # 2. Check file size
    # Read size implicitly via seeking
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)  # Reset cursor

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds size limit of 10MB (file size: {file_size / (1024*1024):.2f}MB)",
        )

    # 3. Magic Byte Validation for PDFs
    if ext == ".pdf":
        magic_bytes = file.file.read(4)
        file.file.seek(0)  # Reset cursor
        if magic_bytes != b"%PDF":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF structure: Header magic bytes do not match %PDF",
            )

    # 4. Ensure storage path exists
    storage_dir = settings.storage_path
    os.makedirs(storage_dir, exist_ok=True)

    # 5. Generate secure UUID filename
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(storage_dir, unique_filename)

    # Save physical file
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 6. Save DB Metadata
        doc_entry = Document(
            user_id=current_user.id,
            filename=unique_filename,
            original_filename=filename,
            file_type=ext,
            file_size_bytes=file_size,
            status="uploaded",
            storage_path=dest_path,
        )
        db.add(doc_entry)
        await db.commit()
        await db.refresh(doc_entry)

        # 7. Queue Celery task for background parsing
        process_document.delay(
            document_id=doc_entry.id, file_path=dest_path, user_id=current_user.id
        )

        return {
            "success": True,
            "data": {
                "id": str(doc_entry.id),
                "filename": doc_entry.filename,
                "original_filename": doc_entry.original_filename,
                "file_type": doc_entry.file_type,
                "file_size_bytes": doc_entry.file_size_bytes,
                "status": doc_entry.status,
                "created_at": doc_entry.created_at.isoformat(),
            },
            "message": "Document uploaded successfully and queued for intelligent parsing.",
        }
    except Exception as e:
        # Cleanup file if DB transaction failed
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failure during upload: {str(e)}",
        )


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List all user documents",
    description="Returns a list of all documents uploaded by the currently authenticated user.",
    responses={401: {"description": "Not authenticated", "model": ErrorResponse}},
)
async def list_documents(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all uploaded documents belonging to the authenticated user.
    """
    stmt = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    res = await db.execute(stmt)
    docs = res.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "original_filename": doc.original_filename,
                "file_type": doc.file_type,
                "file_size_bytes": doc.file_size_bytes,
                "status": doc.status,
                "chunk_count": doc.chunk_count,
                "error_message": doc.error_message,
                "created_at": doc.created_at.isoformat(),
            }
            for doc in docs
        ],
        "message": "Documents retrieved successfully.",
    }


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details",
    description="Retrieves metadata, status, and chunk details for a specific document.",
    responses={
        401: {"description": "Not authenticated", "model": ErrorResponse},
        403: {
            "description": "Access forbidden: You do not own this document",
            "model": ErrorResponse,
        },
        404: {"description": "Document not found", "model": ErrorResponse},
    },
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve specific document metadata with ownership protection check.
    """
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    if doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this document.",
        )

    return {
        "success": True,
        "data": {
            "id": str(doc.id),
            "filename": doc.filename,
            "original_filename": doc.original_filename,
            "file_type": doc.file_type,
            "file_size_bytes": doc.file_size_bytes,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
            "error_message": doc.error_message,
            "created_at": doc.created_at.isoformat(),
        },
        "message": "Document retrieved successfully.",
    }


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete a document",
    description="Deletes document physical file, DB records, and vector embeddings from vector store.",
    responses={
        401: {"description": "Not authenticated", "model": ErrorResponse},
        403: {
            "description": "Access forbidden: You do not own this document",
            "model": ErrorResponse,
        },
        404: {"description": "Document not found", "model": ErrorResponse},
    },
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete document, cleaning up storage file, DB records, and vector embeddings.
    """
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    if doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this document.",
        )

    # 1. Delete Supabase pgvector embeddings
    vector_service = get_pgvector_service()
    await vector_service.delete_by_filter(
        "documents", {"document_id": str(document_id)}
    )

    # 2. Delete physical storage file if it exists
    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except OSError as e:
            import logging
            logging.getLogger(__name__).warning(f"Ignored error in OSError: {e}")

    # 3. Delete from DB
    await db.delete(doc)
    await db.commit()

    return {
        "success": True,
        "data": {"id": str(document_id)},
        "message": "Document and all corresponding semantic vectors successfully deleted.",
    }


@router.post(
    "/query",
    response_model=DocumentQueryResponse,
    summary="Semantic document query",
    description="Performs a vector search over the user's uploaded documents.",
    responses={
        401: {"description": "Not authenticated", "model": ErrorResponse},
        500: {"description": "Semantic query search error", "model": ErrorResponse},
    },
)
async def query_documents(
    payload: QueryPayload, current_user: User = Depends(get_current_active_user)
):
    """
    Perform vector semantic search over user documents.
    """
    doc_service = get_document_service()
    results = await doc_service.query_documents(
        query=payload.query, user_id=current_user.id, doc_ids=payload.doc_ids, limit=5
    )

    return {
        "success": True,
        "data": results,
        "message": "Semantic document search completed.",
    }
