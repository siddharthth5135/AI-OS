from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class DocumentUploadResponseData(BaseModel):
    """Document metadata returned after uploading."""

    id: str = Field(..., description="Unique document UUID")
    filename: str = Field(..., description="Secure storage filename")
    original_filename: str = Field(
        ..., description="Original filename uploaded by the user"
    )
    file_type: str = Field(..., description="File extension (e.g. .pdf, .txt, .md)")
    file_size_bytes: int = Field(..., description="File size in bytes")
    status: str = Field(
        ..., description="Parsing status (uploaded, parsing, indexed, failed)"
    )
    created_at: str = Field(..., description="ISO 8601 creation timestamp")


class DocumentUploadResponse(BaseResponse[DocumentUploadResponseData]):
    """Standard API response wrapping DocumentUploadResponseData."""

    pass


class DocumentDetailData(BaseModel):
    """Full document model details with parsing metadata."""

    id: str = Field(..., description="Unique document UUID")
    filename: str = Field(..., description="Secure storage filename")
    original_filename: str = Field(..., description="Original user filename")
    file_type: str = Field(..., description="File extension")
    file_size_bytes: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Parsing status")
    chunk_count: Optional[int] = Field(
        None, description="Number of text chunks extracted"
    )
    error_message: Optional[str] = Field(
        None, description="Parsing error message if status is failed"
    )
    created_at: str = Field(..., description="ISO 8601 creation timestamp")


class DocumentDetailResponse(BaseResponse[DocumentDetailData]):
    """Standard API response wrapping DocumentDetailData."""

    pass


class DocumentListResponse(BaseResponse[List[DocumentDetailData]]):
    """Standard API response wrapping a list of DocumentDetailData."""

    pass


class DocumentDeleteResponseData(BaseModel):
    """Payload returned after deleting a document."""

    id: str = Field(..., description="Deleted document UUID")


class DocumentDeleteResponse(BaseResponse[DocumentDeleteResponseData]):
    """Standard API response wrapping DocumentDeleteResponseData."""

    pass


class DocumentQueryResponseItem(BaseModel):
    """Single semantic search chunk match."""

    text: str = Field(..., description="Text segment snippet")
    score: float = Field(
        ..., description="Cosine similarity relevance score (0.0 to 1.0)"
    )
    document_id: str = Field(..., description="Source document UUID")
    filename: str = Field(..., description="Source document filename")
    metadata: Dict[str, Any] = Field(
        default={}, description="Arbitrary chunk metadata details"
    )


class DocumentQueryResponse(BaseResponse[List[DocumentQueryResponseItem]]):
    """Standard API response wrapping a list of semantic search matches."""

    pass
