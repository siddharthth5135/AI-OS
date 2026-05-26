import asyncio
import time
import typing
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select

from app.agents.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.logging.logger import get_logger
from app.core.observability.metrics import (LLM_TOKENS, TASK_LATENCY,
                                            TASKS_TOTAL)
from app.db.database import AsyncSessionLocal
from app.db.models.chat import Chat
from app.db.models.task import Task
from app.services.documents.document_service import DocumentService
from app.services.memory.memory_service import MemoryService
from app.services.orchestration.task_classifier import (TaskClassification,
                                                        TaskClassifier,
                                                        TaskType)

logger = get_logger("ai_os.orchestration.orchestrator")


@dataclass
class OrchestratorResult:
    task_id: str
    response: str
    agent_used: str
    memory_used: bool
    documents_used: bool
    tokens_used: int
    latency_ms: int
    sources: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class StreamEvent:
    type: str
    data: dict


class AgentOrchestrator:
    def __init__(self):
        self._classifier = TaskClassifier()
        self._agents = {}
        self._memory_service = MemoryService()
        self._doc_service = DocumentService()

    async def initialize(self) -> typing.Any:
        """
        Import and dynamically register ResearchAgent, CodeAgent, DocumentAgent, MemoryAgent, and WorkflowAgent.
        """
        try:
            from app.agents.code.agent import CodeAgent
            from app.agents.document.agent import DocumentAgent
            from app.agents.memory.agent import MemoryAgent
            from app.agents.research.agent import ResearchAgent
            from app.agents.workflow.agent import WorkflowAgent

            self._agents["research"] = ResearchAgent()
            self._agents["code"] = CodeAgent()
            self._agents["document"] = DocumentAgent()
            self._agents["memory"] = MemoryAgent()
            self._agents["workflow"] = WorkflowAgent()

            logger.info(
                "orchestrator.initialized_successfully",
                registered_agents=list(self._agents.keys()),
            )
        except Exception as e:
            logger.critical("orchestrator.initialization_failed", error=str(e))
            raise

    async def process_task(
        self,
        query: str,
        user_id: uuid.UUID,
        session_id: str,
        task_id: str,
        context: Optional[dict] = None,
        force_agent: Optional[str] = None,
        **kwargs,
    ) -> OrchestratorResult:
        """
        Automatically generated docstring.
        """
        logger.info(
            "orchestrator.process_task_start",
            task_id=task_id,
            user_id=str(user_id),
            force_agent=force_agent,
        )

        # Resolve task type from DB to record labels accurately
        task_type = "chat"
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Task.task_type).where(Task.id == uuid.UUID(task_id))
                res = await session.execute(stmt)
                task_type = res.scalar_one_or_none() or "chat"
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Ignored error in Exception: {e}")

        # 1. Classify
        if force_agent:
            classification = TaskClassification(
                primary_agent=TaskType(force_agent),
                confidence=1.0,
                reasoning=f"Forced execution of {force_agent} agent.",
                requires_memory=False,
                requires_documents=False,
                estimated_complexity="medium",
            )
        else:
            try:
                classification = await self._classifier.classify(query, context)
            except Exception as e:
                logger.error(
                    "orchestrator.classification_failed_fallback_research", error=str(e)
                )
                classification = TaskClassification(
                    primary_agent=TaskType.RESEARCH,
                    confidence=0.5,
                    reasoning="Fallback to research due to classification error.",
                )

        TASKS_TOTAL.labels(
            type=classification.primary_agent.value, status="started"
        ).inc()

        # 2. Update task status to running
        await self._update_task_status(
            task_id, "running", agent_used=classification.primary_agent.value
        )

        # 3. Parallel Retrieval of memories and document chunks
        requires_memory = True
        requires_documents = (
            getattr(classification, "requires_documents", False)
            or classification.primary_agent.value == "document"
        )

        doc_ids = context.get("doc_ids") if context else None

        async def noop() -> typing.Any:
            """
            Automatically generated docstring.
            """
            return []

        try:
            memories, doc_chunks = await asyncio.gather(
                (
                    self._memory_service.retrieve_relevant(
                        query, str(user_id), min_score=-1.0
                    )
                    if requires_memory
                    else noop()
                ),
                (
                    self._doc_service.query_documents(query, user_id, doc_ids)
                    if requires_documents
                    else noop()
                ),
            )
        except Exception as e:
            logger.error("orchestrator.retrieval_failed", error=str(e))
            memories, doc_chunks = [], []

        # 4. Get Agent
        agent: BaseAgent = self._agents.get(
            classification.primary_agent.value, self._agents["research"]
        )

        # 5. Execute Agent with a strict 45-second timeout
        start_time = time.time()
        try:
            chat_history = await self._memory_service.get_short_term(
                str(user_id), session_id
            )
            agent_ctx = AgentContext(
                memories=memories,
                doc_chunks=doc_chunks,
                chat_history=chat_history,
                session_id=session_id,
                user_id=str(user_id),
            )

            with TASK_LATENCY.labels(
                type=task_type, agent=classification.primary_agent.value
            ).time():
                result: AgentResult = await asyncio.wait_for(
                    agent.execute(query, agent_ctx, stream=False, **kwargs),
                    timeout=45.0,
                )
            latency_ms = int((time.time() - start_time) * 1000)

            # 6. Store chat message history
            await self._store_chat(
                user_id=user_id,
                session_id=session_id,
                query=query,
                response=result.response,
                agent_type=result.agent_type,
                tokens_used=result.tokens_used,
                latency_ms=latency_ms,
            )

            # 7. Append user query & assistant response to short-term session memory
            try:
                await self._memory_service.append_to_session(
                    user_id=str(user_id),
                    session_id=session_id,
                    message={"role": "user", "content": query},
                )
                await self._memory_service.append_to_session(
                    user_id=str(user_id),
                    session_id=session_id,
                    message={"role": "assistant", "content": result.response},
                )
            except Exception as e:
                logger.error("orchestrator.append_session_memory_failed", error=str(e))

            # 8. Dispatch long term memory task if response meets importance threshold
            try:
                importance = await self._memory_service.score_importance(
                    result.response
                )
                if importance >= self._memory_service.IMPORTANCE_THRESHOLD:
                    from app.workers.embedding_worker import \
                        generate_and_store_embedding

                    generate_and_store_embedding.delay(
                        content=result.response,
                        user_id=str(user_id),
                        memory_type="assistant_response",
                        summary=None,
                    )
            except Exception as e:
                logger.error(
                    "orchestrator.dispatch_long_term_memory_failed", error=str(e)
                )

            # 9. Update task completed
            await self._update_task_completed(task_id, result)

            TASKS_TOTAL.labels(
                type=classification.primary_agent.value, status="completed"
            ).inc()
            LLM_TOKENS.labels(
                agent=classification.primary_agent.value, direction="total"
            ).inc(result.tokens_used)

            logger.info(
                "orchestrator.process_task_success",
                task_id=task_id,
                agent_used=result.agent_type,
            )
            return OrchestratorResult(
                task_id=task_id,
                response=result.response,
                agent_used=result.agent_type,
                memory_used=requires_memory,
                documents_used=requires_documents,
                tokens_used=result.tokens_used,
                latency_ms=latency_ms,
                sources=result.sources,
                metadata=result.metadata,
            )

        except Exception as e:
            TASKS_TOTAL.labels(
                type=classification.primary_agent.value, status="failed"
            ).inc()
            logger.error(
                "orchestrator.process_task_exception", task_id=task_id, error=str(e)
            )
            await self._update_task_failed(task_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent execution failed: {str(e)}",
            )

    async def process_stream(
        self,
        query: str,
        user_id: uuid.UUID,
        session_id: str,
        task_id: str,
        context: Optional[dict] = None,
        force_agent: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Automatically generated docstring.
        """
        logger.info(
            "orchestrator.process_stream_start",
            task_id=task_id,
            user_id=str(user_id),
            force_agent=force_agent,
        )

        # Resolve task type from DB to record labels accurately
        task_type = "chat"
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Task.task_type).where(Task.id == uuid.UUID(task_id))
                res = await session.execute(stmt)
                task_type = res.scalar_one_or_none() or "chat"
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Ignored error in Exception: {e}")

        start_time = time.time()
        try:
            yield StreamEvent("task_update", {"status": "classifying"})

            if force_agent:
                classification = TaskClassification(
                    primary_agent=TaskType(force_agent),
                    confidence=1.0,
                    reasoning=f"Forced execution of {force_agent} agent.",
                    requires_memory=False,
                    requires_documents=False,
                    estimated_complexity="medium",
                )
            else:
                try:
                    classification = await self._classifier.classify(query, context)
                except Exception as e:
                    logger.error(
                        "orchestrator.stream_classification_failed_fallback_research",
                        error=str(e),
                    )
                    classification = TaskClassification(
                        primary_agent=TaskType.RESEARCH,
                        confidence=0.5,
                        reasoning="Fallback to research due to classification error.",
                    )

            TASKS_TOTAL.labels(
                type=classification.primary_agent.value, status="started"
            ).inc()

            yield StreamEvent(
                "task_update",
                {"status": "routing", "agent": classification.primary_agent.value},
            )
            await self._update_task_status(
                task_id, "running", classification.primary_agent.value
            )

            async def _noop_list():
                return []

            requires_memory = getattr(classification, "requires_memory", True)
            requires_documents = (
                getattr(classification, "requires_documents", False)
                or classification.primary_agent.value == "document"
            )

            mem_coro = (
                self._memory_service.retrieve_relevant(query, str(user_id), limit=5)
                if requires_memory
                else _noop_list()
            )
            doc_coro = (
                self._doc_service.query_documents(
                    query, user_id, context.get("doc_ids") if context else None
                )
                if requires_documents
                else _noop_list()
            )

            memories, doc_chunks = await asyncio.gather(mem_coro, doc_coro)

            yield StreamEvent(
                "task_update",
                {
                    "status": "generating",
                    "context_items": len(memories) + len(doc_chunks),
                },
            )

            agent: BaseAgent = self._agents.get(
                classification.primary_agent.value, self._agents["research"]
            )
            agent_ctx = AgentContext(
                memories=memories,
                doc_chunks=doc_chunks,
                session_id=session_id,
                user_id=str(user_id),
            )

            stream_or_result = await agent.execute(
                query, agent_ctx, stream=True, **kwargs
            )

            full_response = ""
            total_tokens = 0
            if hasattr(stream_or_result, "__aiter__"):
                async for chunk in stream_or_result:
                    if getattr(chunk, "is_final", False):
                        total_tokens = getattr(chunk, "total_tokens", 0)
                    else:
                        yield StreamEvent("token", {"text": chunk.text})
                        full_response += chunk.text
            else:
                full_response = stream_or_result.response
                total_tokens = stream_or_result.tokens_used
                for word in full_response.split(" "):
                    yield StreamEvent("token", {"text": word + " "})

            latency = int((time.time() - start_time) * 1000)

            await self._store_chat(
                user_id,
                session_id,
                query,
                full_response,
                classification.primary_agent.value,
                total_tokens,
                latency,
            )

            await self._update_task_completed(
                task_id,
                AgentResult(
                    response=full_response,
                    agent_type=classification.primary_agent.value,
                    tokens_used=total_tokens,
                    latency_ms=latency,
                    confidence=0.95,
                ),
            )

            try:
                await self._memory_service.append_to_session(
                    str(user_id), session_id, {"role": "user", "content": query}
                )
                await self._memory_service.append_to_session(
                    str(user_id),
                    session_id,
                    {"role": "assistant", "content": full_response},
                )
            except Exception as e:
                logger.error(
                    "orchestrator.stream_append_session_memory_failed", error=str(e)
                )

            try:
                importance = await self._memory_service.score_importance(full_response)
                if importance >= self._memory_service.IMPORTANCE_THRESHOLD:
                    from app.workers.embedding_worker import \
                        generate_and_store_embedding

                    generate_and_store_embedding.delay(
                        content=full_response,
                        user_id=str(user_id),
                        memory_type="assistant_response",
                        summary=None,
                    )
            except Exception as e:
                logger.error(
                    "orchestrator.stream_dispatch_long_term_memory_failed", error=str(e)
                )

            TASKS_TOTAL.labels(
                type=classification.primary_agent.value, status="completed"
            ).inc()
            TASK_LATENCY.labels(
                type=task_type, agent=classification.primary_agent.value
            ).observe(latency / 1000.0)
            LLM_TOKENS.labels(
                agent=classification.primary_agent.value, direction="total"
            ).inc(total_tokens)

            yield StreamEvent(
                "task_completed",
                {
                    "task_id": str(task_id),
                    "tokens_used": total_tokens,
                    "agent_used": classification.primary_agent.value,
                    "latency_ms": latency,
                },
            )

        except (asyncio.CancelledError, GeneratorExit) as e:
            TASKS_TOTAL.labels(
                type=classification.primary_agent.value, status="failed"
            ).inc()
            logger.warning(
                "orchestrator.process_stream_cancelled",
                task_id=task_id,
                error_type=type(e).__name__,
            )
            await self._update_task_failed(
                task_id, f"Client stream disconnected: {type(e).__name__}"
            )
            raise
        except Exception as e:
            TASKS_TOTAL.labels(
                type=classification.primary_agent.value, status="failed"
            ).inc()
            logger.error(
                "orchestrator.process_stream_exception", task_id=task_id, error=str(e)
            )
            await self._update_task_failed(task_id, str(e))
            yield StreamEvent(
                "error", {"message": str(e), "code": "orchestration_error"}
            )

    # Private Helpers for Database Interactions
    async def _update_task_status(
        self, task_id: str, status_str: str, agent_used: Optional[str] = None
    ):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = select(Task).where(Task.id == uuid.UUID(task_id))
                res = await session.execute(stmt)
                task = res.scalar_one_or_none()
                if task:
                    task.status = status_str
                    if agent_used:
                        task.agent_used = agent_used
                    await session.commit()

    async def _update_task_completed(self, task_id: str, result: AgentResult):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = select(Task).where(Task.id == uuid.UUID(task_id))
                res = await session.execute(stmt)
                task = res.scalar_one_or_none()
                if task:
                    task.status = "completed"
                    task.result_data = {
                        "response": result.response,
                        "confidence": result.confidence,
                        "sources": result.sources,
                        "metadata": result.metadata,
                    }
                    task.tokens_used = result.tokens_used
                    task.processing_time_ms = result.latency_ms
                    task.completed_at = datetime.now(timezone.utc)
                    await session.commit()

    async def _update_task_failed(self, task_id: str, error_msg: str):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = select(Task).where(Task.id == uuid.UUID(task_id))
                res = await session.execute(stmt)
                task = res.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error_message = error_msg
                    task.completed_at = datetime.now(timezone.utc)
                    await session.commit()

    async def _store_chat(
        self,
        user_id: uuid.UUID,
        session_id: str,
        query: str,
        response: str,
        agent_type: str,
        tokens_used: int = 0,
        latency_ms: int = 0,
    ):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # User message
                user_msg = Chat(
                    user_id=user_id,
                    conversation_id=session_id,
                    role="user",
                    content=query,
                    agent_type=agent_type,
                )
                # Assistant response
                assistant_msg = Chat(
                    user_id=user_id,
                    conversation_id=session_id,
                    role="assistant",
                    content=response,
                    agent_type=agent_type,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                )
                session.add(user_msg)
                session.add(assistant_msg)
                await session.commit()
