import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, UUIDPKMixin, TimestampMixin

class Document(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(512), unique=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(50))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), index=True, default="uploaded")
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    storage_path: Mapped[Optional[str]] = mapped_column(Text)
    pgvector_collection: Mapped[Optional[str]] = mapped_column(String(255))
    started_processing_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_processing_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user = relationship("User", lazy="selectin")
