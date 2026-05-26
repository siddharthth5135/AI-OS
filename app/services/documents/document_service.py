import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.services.documents.chunker import DocumentChunker
from app.services.documents.text_extractor import TextExtractor
from app.services.embeddings.embedding_service import get_embedding_service
from app.vectorstore.pgvector_service import PointStruct, get_pgvector_service


class DocumentService:
    def __init__(self):
        self.extractor = TextExtractor()
        self.chunker = DocumentChunker()
        self.embedding_service = get_embedding_service()
        self.vector_service = get_pgvector_service()

    async def process_document(
        self, doc_id: uuid.UUID, file_path: str, user_id: uuid.UUID, db: AsyncSession
    ):
        """
        Runs the full document intelligence pipeline:
        status=processing -> text extraction -> chunking -> batch embedding -> pgvector upsert -> status=indexed.
        """
        # Fetch document from DB
        stmt = select(Document).where(Document.id == doc_id)
        res = await db.execute(stmt)
        doc = res.scalar_one_or_none()
        if not doc:
            return

        try:
            # 1. Update status to processing
            doc.status = "processing"
            doc.started_processing_at = datetime.now(timezone.utc)
            await db.commit()

            # 2. Extract full text
            extracted = await self.extractor.extract(file_path, doc.file_type)

            # 3. Chunk text into overlapping segments
            chunk_metadata = {
                "user_id": str(user_id),
                "document_id": str(doc_id),
                "filename": doc.filename,
                "original_filename": doc.original_filename,
            }
            chunks = self.chunker.chunk_text(
                extracted.full_text, metadata=chunk_metadata
            )

            if not chunks:
                raise ValueError("Document yielded no text chunks to index.")

            # 4. Generate batch embeddings
            chunk_texts = [c.text for c in chunks]
            embeddings = await self.embedding_service.embed_batch(chunk_texts)

            # 5. Build pgvector PointStructs
            points = []
            for i, chunk in enumerate(chunks):
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embeddings[i],
                        payload={
                            "user_id": str(user_id),
                            "document_id": str(doc_id),
                            "text": chunk.text,
                            "chunk_index": chunk.chunk_index,
                            "filename": doc.filename,
                            "original_filename": doc.original_filename,
                        },
                    )
                )

            # 6. Upsert points to 'documents' vector collection
            await self.vector_service.upsert_points("documents", points)

            # 7. Complete database status update
            doc.status = "indexed"
            doc.chunk_count = len(chunks)
            doc.completed_processing_at = datetime.now(timezone.utc)
            await db.commit()

            try:
                from app.core.observability.metrics import DOCS_PROCESSED

                DOCS_PROCESSED.labels(file_type=doc.file_type, status="indexed").inc()
            except Exception:
                pass

        except Exception as e:
            # Revert status on failure
            doc.status = "failed"
            doc.error_message = str(e)[:500]
            await db.commit()

            try:
                from app.core.observability.metrics import DOCS_PROCESSED

                DOCS_PROCESSED.labels(file_type=doc.file_type, status="failed").inc()
            except Exception:
                pass

            raise e

    async def query_documents(
        self,
        query: str,
        user_id: uuid.UUID,
        doc_ids: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[dict]:
        """
        Embed the search query and semantic search the Supabase pgvector 'documents' collection.
        Filters by user ownership, and optionally a specific list of document IDs.
        """
        # 1. Embed query with instruction prefix
        query_vector = await self.embedding_service.embed_query(query)

        # 2. Build metadata filter for the vector store
        # Containment payload matching structure
        filter_payload = {"user_id": str(user_id)}

        # If we have a single doc_id filter we can append it directly
        if doc_ids and len(doc_ids) == 1:
            filter_payload["document_id"] = str(doc_ids[0])

        # 3. Query pgvector store
        matches = await self.vector_service.search(
            collection="documents",
            vector=query_vector,
            limit=limit,
            filter=filter_payload,
            score_threshold=0.3,
        )

        # 4. Handle multiple doc_ids post-filtering if multiple doc_ids are queried
        results = []
        for match in matches:
            payload = match.get("payload", {})
            doc_id = payload.get("document_id")

            # Post filter check for multiple doc IDs
            if doc_ids and len(doc_ids) > 1 and doc_id not in doc_ids:
                continue

            results.append(
                {
                    "text": payload.get("text", ""),
                    "score": match.get("score", 0.0),
                    "filename": payload.get("original_filename")
                    or payload.get("filename", "unknown"),
                    "chunk_index": payload.get("chunk_index", 0),
                }
            )

        return results


_document_service = DocumentService()


def get_document_service() -> DocumentService:
    return _document_service
