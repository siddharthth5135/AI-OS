import asyncio
import os

import pytest

# Set environment variables for tests before any app module imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_integration_temp.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = (
    "3266d6ed5611930bd34145d7ad95781fd895058a507cd7d24500b9daf711ff07"
)
os.environ["GEMINI_API_KEY"] = "AIzaSyCYvZctURglhYPDxZeXbW2G9dXxob3VNoI"

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.ext.compiler import compiles

from app.db.models.base import Base


# Register custom compiler to render JSONB as JSON in SQLite
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


from app.db.database import get_db as get_db_core
from app.db.models.chat import Chat
from app.db.models.document import Document
from app.db.models.memory_entry import MemoryEntry
from app.db.models.task import Task
# Import all models to register them on Base.metadata
from app.db.models.user import User
from app.db.models.user_session import UserSession
from app.db.session.database import get_db as get_db_session
from app.main import app
from app.vectorstore.pgvector_service import PgVectorService

TEST_DATABASE_URL = "sqlite+aiosqlite:///test_integration_temp.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create session-wide event loop for async tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a temporary local SQLite file engine and initialize tables."""
    # Ensure any old test database is deleted first
    if os.path.exists("test_integration_temp.db"):
        try:
            os.remove("test_integration_temp.db")
        except OSError:
            pass

    engine = create_async_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )

    # Patch global engines and session makers
    import app.db.database
    import app.db.session.database

    test_session_local = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    app.db.database.engine = engine
    app.db.database.AsyncSessionLocal = test_session_local
    app.db.session.database.engine = engine
    app.db.session.database.AsyncSessionLocal = test_session_local

    # Patch module level imports of AsyncSessionLocal to ensure they use SQLite with check_same_thread=False
    import app.api.routes.observability
    import app.services.llm.token_tracker
    import app.services.memory.memory_service
    import app.services.orchestration.orchestrator
    import app.workers.cleanup_worker
    import app.workers.document_worker

    app.services.memory.memory_service.AsyncSessionLocal = test_session_local
    app.services.orchestration.orchestrator.AsyncSessionLocal = test_session_local
    app.services.llm.token_tracker.AsyncSessionLocal = test_session_local
    app.api.routes.observability.AsyncSessionLocal = test_session_local
    app.workers.document_worker.AsyncSessionLocal = test_session_local
    app.workers.cleanup_worker.AsyncSessionLocal = test_session_local

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()

    # Clean up test database file
    if os.path.exists("test_integration_temp.db"):
        try:
            os.remove("test_integration_temp.db")
        except OSError:
            pass


@pytest.fixture(scope="function")
async def db_session(test_engine):
    """Provide a clean transaction database session per test function."""
    import app.db.database

    async with app.db.database.AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
async def override_db(db_session):
    """Override standard get_db dependencies with the test SQLite session."""

    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db_core] = _get_test_db
    app.dependency_overrides[get_db_session] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def init_app_state(test_engine):
    """Initializes app state variables that would normally be set by lifespan startup."""
    import time

    from app.services.orchestration.orchestrator import AgentOrchestrator

    orch = AgentOrchestrator()
    await orch.initialize()
    app.state.orchestrator = orch
    app.state.start_time = time.time()
    yield


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Mocks RedisClient globally to prevent external connections and simulate Redis in memory."""
    import json
    from typing import Any

    from app.core.cache.redis_client import RedisClient

    storage = {}

    async def mock_connect(self, url, max_connections=20):
        pass

    async def mock_disconnect(self):
        pass

    async def mock_ping(self) -> bool:
        return True

    async def mock_get(self, key: str):
        return storage.get(key)

    async def mock_set(self, key: str, value: str, ttl: int = None):
        storage[key] = value

    async def mock_delete(self, key: str):
        storage.pop(key, None)

    async def mock_exists(self, key: str) -> bool:
        return key in storage

    async def mock_incr(self, key: str) -> int:
        val = int(storage.get(key, 0)) + 1
        storage[key] = str(val)
        return val

    async def mock_incrby(self, key: str, amount: int) -> int:
        val = int(storage.get(key, 0)) + amount
        storage[key] = str(val)
        return val

    async def mock_get_json(self, key: str):
        val = storage.get(key)
        return json.loads(val) if val else None

    async def mock_set_json(self, key: str, value: Any, ttl: int = None):
        storage[key] = json.dumps(value)

    async def mock_publish(self, channel: str, message: str):
        pass

    async def mock_keys(self, pattern: str):
        return list(storage.keys())

    monkeypatch.setattr(RedisClient, "connect", mock_connect)
    monkeypatch.setattr(RedisClient, "disconnect", mock_disconnect)
    monkeypatch.setattr(RedisClient, "ping", mock_ping)
    monkeypatch.setattr(RedisClient, "get", mock_get)
    monkeypatch.setattr(RedisClient, "set", mock_set)
    monkeypatch.setattr(RedisClient, "delete", mock_delete)
    monkeypatch.setattr(RedisClient, "exists", mock_exists)
    monkeypatch.setattr(RedisClient, "incr", mock_incr)
    monkeypatch.setattr(RedisClient, "incrby", mock_incrby)
    monkeypatch.setattr(RedisClient, "get_json", mock_get_json)
    monkeypatch.setattr(RedisClient, "set_json", mock_set_json)
    monkeypatch.setattr(RedisClient, "publish", mock_publish)
    monkeypatch.setattr(RedisClient, "keys", mock_keys)


@pytest.fixture(autouse=True)
def mock_celery_task(monkeypatch):
    """Mocks Celery tasks to run asynchronously in-process during test."""
    from app.workers.document_worker import (_async_process_document,
                                             process_document)
    from app.workers.embedding_worker import (_async_embed,
                                              generate_and_store_embedding)

    def mock_delay(document_id, file_path, user_id):
        loop = asyncio.get_running_loop()
        loop.create_task(_async_process_document(document_id, file_path, user_id))

    def mock_embed_delay(content, user_id, memory_type, summary=None):
        loop = asyncio.get_running_loop()
        loop.create_task(_async_embed(content, user_id, memory_type, summary))

    monkeypatch.setattr(process_document, "delay", mock_delay)
    monkeypatch.setattr(generate_and_store_embedding, "delay", mock_embed_delay)


@pytest.fixture(autouse=True)
def mock_pgvector(monkeypatch):
    """Mocks PgVectorService methods to bypass Postgres-specific operators on SQLite."""

    async def mock_initialize(self):
        pass

    async def mock_ensure_collections(self):
        pass

    async def mock_upsert_points(self, collection, points):
        pass

    async def mock_delete_by_filter(self, collection, filter):
        pass

    async def mock_count(self, collection, filter=None):
        return 1

    async def mock_search(
        self, collection, vector, limit=5, filter=None, score_threshold=0.3
    ):
        if collection == "documents":
            return [
                {
                    "id": "chunk_1",
                    "payload": {
                        "text": "Consistency, Availability, and Partition Tolerance in CAP theorem.",
                        "document_id": "test-doc-id",
                        "filename": "test_doc.pdf",
                    },
                    "score": 0.9,
                }
            ]
        elif collection == "user_memory":
            return [
                {
                    "id": "fact_1",
                    "payload": {"text": "User prefers python development preference"},
                    "score": 0.85,
                }
            ]
        return []

    monkeypatch.setattr(PgVectorService, "initialize", mock_initialize)
    monkeypatch.setattr(PgVectorService, "ensure_collections", mock_ensure_collections)
    monkeypatch.setattr(PgVectorService, "upsert_points", mock_upsert_points)
    monkeypatch.setattr(PgVectorService, "delete_by_filter", mock_delete_by_filter)
    monkeypatch.setattr(PgVectorService, "count", mock_count)
    monkeypatch.setattr(PgVectorService, "search", mock_search)


@pytest.fixture(autouse=True)
def mock_embeddings(monkeypatch):
    """Mocks EmbeddingService methods to avoid loading Hugging Face models in tests."""
    from app.services.embeddings.embedding_service import EmbeddingService

    async def mock_initialize(self):
        pass

    async def mock_embed_text(self, text):
        return [0.0] * 384

    async def mock_embed_batch(self, texts, batch_size=32):
        return [[0.0] * 384 for _ in texts]

    async def mock_embed_query(self, query):
        return [0.0] * 384

    monkeypatch.setattr(EmbeddingService, "initialize", mock_initialize)
    monkeypatch.setattr(EmbeddingService, "embed_text", mock_embed_text)
    monkeypatch.setattr(EmbeddingService, "embed_batch", mock_embed_batch)
    monkeypatch.setattr(EmbeddingService, "embed_query", mock_embed_query)
