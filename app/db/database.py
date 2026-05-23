from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config.settings import settings


logger = structlog.get_logger("ai_os.db")

# Create the async engine with NullPool to avoid connection pooling and event loop conflicts
engine = create_async_engine(
    settings.async_database_url,
    poolclass=NullPool,
    echo=settings.debug,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async SQLAlchemy session.
    Automatically handles rollback on exceptions and cleanup.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error("database.session_error", error=str(e))
            await session.rollback()
            raise
        finally:
            await session.close()
