import asyncio
from app.workers.celery_app import celery_app
from app.db.session.database import AsyncSessionLocal
from app.db.models.user_session import UserSession
from sqlalchemy import update
from datetime import datetime, timezone

async def _async_expire_old_sessions():
    from app.db.session.database import engine
    try:
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            stmt = (
                update(UserSession)
                .where(UserSession.expires_at < now)
                .where(UserSession.is_revoked == False)
                .values(is_revoked=True)
            )
            await db.execute(stmt)
            await db.commit()
    finally:
        await engine.dispose()

@celery_app.task
def expire_old_sessions():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_async_expire_old_sessions())
    finally:
        loop.close()
