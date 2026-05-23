import asyncio
from app.workers.celery_app import celery_app

async def _async_embed(content, user_id, memory_type, summary):
    from app.services.memory.memory_service import MemoryService
    from app.db.session.database import AsyncSessionLocal, engine
    
    memory_service = MemoryService()
    async with AsyncSessionLocal() as db:
        try:
            entry = await memory_service.store_long_term(
                user_id=user_id,
                content=content,
                memory_type=memory_type,
                db=db,
                summary=summary
            )
            return {"embedding_id": entry.embedding_id, "status": "stored"}
        except Exception as e:
            raise e

@celery_app.task(bind=True, max_retries=3, time_limit=180)
def generate_and_store_embedding(self, content, user_id, memory_type, summary=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_async_embed(content, user_id, memory_type, summary))
    except Exception as exc:
        raise self.retry(exc=exc)
    finally:
        loop.close()
