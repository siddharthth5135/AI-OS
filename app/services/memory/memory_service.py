import datetime
import uuid
from typing import List, Optional

from sqlalchemy import select

from app.core.cache.redis_client import get_redis
from app.db.models.memory_entry import MemoryEntry
from app.db.session.database import AsyncSessionLocal
from app.services.embeddings.embedding_service import get_embedding_service
from app.vectorstore.pgvector_service import PointStruct, get_pgvector_service


class MemoryService:
    SHORT_TTL = 3600
    MAX_MSGS = 20
    IMPORTANCE_THRESHOLD = 0.6

    async def store_short_term(
        self, user_id: str, session_id: str, messages: List[dict], ttl: int = 3600
    ):
        """
        Store a list of messages in Redis for a specific user and session.
        """
        redis = get_redis()
        key = redis.make_key("memory:short", user_id, session_id)
        await redis.set_json(key, messages, ttl=ttl)

    async def get_short_term(self, user_id: str, session_id: str) -> List[dict]:
        """
        Retrieve messages from short-term Redis cache.
        """
        redis = get_redis()
        key = redis.make_key("memory:short", user_id, session_id)
        res = await redis.get_json(key)
        return res if res is not None else []

    async def append_to_session(self, user_id: str, session_id: str, message: dict):
        """
        Append a single message to short-term session memory. Truncates to last MAX_MSGS.
        """
        messages = await self.get_short_term(user_id, session_id)
        messages.append(message)
        messages = messages[-self.MAX_MSGS :]
        await self.store_short_term(user_id, session_id, messages, ttl=self.SHORT_TTL)

    async def clear_session(self, user_id: str, session_id: str):
        """
        Clear short-term memory session.
        """
        redis = get_redis()
        key = redis.make_key("memory:short", user_id, session_id)
        await redis.delete(key)

    async def store_long_term(
        self,
        user_id: str,
        content: str,
        memory_type: str,
        db,
        summary: Optional[str] = None,
        importance: float = 0.5,
    ) -> MemoryEntry:
        """
        Store a memory in PostgreSQL DB + pgvector user_memory collection.
        1. embed_text(content)
        2. point_id = str(uuid4())
        3. Create MemoryEntry in DB (flush, refresh)
        4. Upsert to Supabase pgvector "user_memory" with full payload
        5. Update entry.embedding_id; return entry
        """
        # 1. embed_text
        embedding_service = get_embedding_service()
        vector = await embedding_service.embed_text(content)

        # 2. point_id
        point_id = str(uuid.uuid4())

        # 3. Create MemoryEntry in DB (flush, refresh)
        db_user_id = (
            uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        )

        # Calculate dynamic importance if base default or keep passed one
        importance_score = importance
        if importance == 0.5:
            importance_score = await self.score_importance(content)

        entry = MemoryEntry(
            user_id=db_user_id,
            content=content,
            summary=summary,
            embedding_id="",  # Will be updated in step 5
            memory_type=memory_type,
            importance_score=importance_score,
            access_count=0,
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)

        # 4. Upsert to Supabase pgvector "user_memory" with full payload
        vector_service = get_pgvector_service()
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "user_id": str(user_id),
                "content": content,
                "summary": summary,
                "memory_type": memory_type,
                "importance_score": importance_score,
            },
        )

        try:
            await vector_service.upsert_points("user_memory", [point])

            # 5. Update entry.embedding_id
            entry.embedding_id = point_id
            await db.commit()
            await db.refresh(entry)

            try:
                from app.core.observability.metrics import MEMORIES_STORED

                MEMORIES_STORED.inc()
            except Exception:
                pass

            return entry
        except Exception as e:
            await db.rollback()
            raise e

    async def retrieve_relevant(
        self, query: str, user_id: str, limit: int = 5, min_score: float = 0.35
    ) -> List[dict]:
        """
        Semantic search long-term memory for relevant memories matching the query.
        """
        embedding_service = get_embedding_service()
        query_vector = await embedding_service.embed_query(query)

        vector_service = get_pgvector_service()
        matches = await vector_service.search(
            collection="user_memory",
            vector=query_vector,
            limit=limit,
            filter={"user_id": str(user_id)},
            score_threshold=min_score,
        )

        results = []
        if matches:
            # Update access counts and last accessed time in database
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    for m in matches:
                        emb_id = m["id"]
                        stmt = select(MemoryEntry).where(
                            MemoryEntry.embedding_id == emb_id
                        )
                        res = await session.execute(stmt)
                        entry = res.scalar_one_or_none()
                        if entry:
                            entry.access_count += 1
                            entry.last_accessed_at = datetime.datetime.now(
                                datetime.timezone.utc
                            )
                    await session.commit()

            for m in matches:
                payload = m["payload"]
                results.append(
                    {
                        "content": payload.get("content"),
                        "summary": payload.get("summary"),
                        "memory_type": payload.get("memory_type"),
                        "score": m.get("score"),
                        "importance_score": payload.get("importance_score"),
                    }
                )
        return results

    async def get_session_context(
        self, user_id: str, session_id: str, query: str, limit: int = 5
    ) -> List[dict]:
        """
        Merge short-term (last 10) + long-term (top 3) -> return top limit
        """
        # Fetch last 10 messages from short-term memory
        short_term_msgs = await self.get_short_term(user_id, session_id)
        short_term_slice = short_term_msgs[-10:]

        short_term_mems = []
        for msg in short_term_slice:
            content = msg.get("content") or ""
            role = msg.get("role") or ""
            short_term_mems.append(
                {
                    "content": f"{role}: {content}" if role else content,
                    "summary": None,
                    "memory_type": "short_term",
                    "score": 1.0,
                    "importance_score": 0.5,
                }
            )

        # Fetch top 3 relevant memories from long-term memory
        long_term_mems = await self.retrieve_relevant(query, user_id, limit=3)

        # Merge them
        merged = short_term_mems + long_term_mems
        return merged[:limit]

    async def score_importance(self, content: str) -> float:
        """
        Calculate importance score of a memory string.
        0.5 base; +0.15 if len>200; -0.2 if len<50; +0.1 if digits present;
        +0.25 if important words; -0.1 if question; cap [0.1, 1.0]
        """
        score = 0.5
        if len(content) > 200:
            score += 0.15
        if len(content) < 50:
            score -= 0.2
        if any(c.isdigit() for c in content):
            score += 0.1

        important_words = [
            "remember",
            "always",
            "never",
            "prefer",
            "favorite",
            "must",
            "important",
            "key",
            "crucial",
            "essential",
            "identity",
            "name",
            "bio",
            "profile",
        ]
        content_lower = content.lower()
        if any(word in content_lower for word in important_words):
            score += 0.25

        if "?" in content or content_lower.strip().startswith(
            ("what", "how", "why", "who", "where", "when", "can you", "could you")
        ):
            score -= 0.1

        return max(0.1, min(1.0, score))

    async def consolidate_session(self, user_id: str, session_id: str, db) -> int:
        """
        Consolidate short term memory: identify assistant messages with high importance,
        store them as long term, clear short-term memory, and return count stored.
        """
        messages = await self.get_short_term(user_id, session_id)
        stored_count = 0
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                importance = await self.score_importance(content)
                if importance >= self.IMPORTANCE_THRESHOLD:
                    await self.store_long_term(
                        user_id=user_id,
                        content=content,
                        memory_type="assistant_response",
                        db=db,
                        importance=importance,
                    )
                    stored_count += 1
        await self.clear_session(user_id, session_id)
        return stored_count
