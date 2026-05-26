import asyncio
import os

from sqlalchemy import select

from app.db.models.document import Document
from app.db.session.database import AsyncSessionLocal
from app.workers.celery_app import celery_app


async def _async_process_document(document_id, file_path, user_id):
    from app.db.session.database import engine
    from app.services.documents.document_service import get_document_service

    async with AsyncSessionLocal() as db:
        doc = None
        try:
            doc = await db.get(Document, document_id)
            if not doc:
                return

            # Prevent duplicate processing atomically
            if doc.status in ["processing", "indexed"]:
                return

            # Execute processing pipeline via DocumentService
            doc_service = get_document_service()
            await doc_service.process_document(
                doc_id=document_id, file_path=file_path, user_id=user_id, db=db
            )

        except Exception as e:
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                await db.commit()
            raise e
        finally:
            await engine.dispose()
            # Temp files cleaned up on success or failure
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass


@celery_app.task(bind=True, max_retries=2, time_limit=600)
def process_document(self, document_id, file_path, user_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _async_process_document(document_id, file_path, user_id)
        )
    except Exception as exc:
        raise self.retry(exc=exc)
    finally:
        loop.close()
