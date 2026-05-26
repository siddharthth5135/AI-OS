import json
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.logging.logger import get_logger
from app.services.llm.gemini_client import get_llm_client

logger = get_logger("ai_os.orchestration.classifier")


class TaskType(str, Enum):
    RESEARCH = "research"
    CODE = "code"
    DOCUMENT = "document"
    WORKFLOW = "workflow"
    MEMORY = "memory"


class TaskClassification(BaseModel):
    primary_agent: TaskType = Field(
        ..., description="The main agent designed for this task."
    )
    secondary_agents: List[TaskType] = Field(
        default_factory=list, description="Other agents that could support this task."
    )
    confidence: float = Field(
        ..., description="Classification confidence from 0.0 to 1.0."
    )
    reasoning: str = Field(
        ..., description="Explanation of why this agent was selected."
    )
    requires_memory: bool = Field(
        default=False, description="Whether memory retrieval is required."
    )
    requires_documents: bool = Field(
        default=False, description="Whether document context retrieval is required."
    )
    estimated_complexity: str = Field(
        default="medium", description="Estimated task complexity (low, medium, high)."
    )


class TaskClassifier:
    CODE_SIGNALS = [
        "def ",
        "class ",
        "```",
        "import ",
        "function",
        "debug",
        "error",
        "bug",
        "fix",
        "syntax",
        "python",
        "javascript",
        "implement",
        "algorithm",
        "traceback",
        "write",
        "async",
        "code",
        "reader",
        "program",
        "develop",
        "show me code",
    ]
    DOCUMENT_SIGNALS = [
        "document",
        "pdf",
        "file",
        "upload",
        "what does the file",
        "from the doc",
        "summarize",
    ]
    MEMORY_SIGNALS = [
        "remember",
        "last time",
        "previous",
        "we discussed",
        "earlier",
        "what did i",
        "prefs",
        "preferences",
        "know about me",
        "about my",
    ]
    WORKFLOW_SIGNALS = [
        r"first.*then",
        "step by step",
        "and after",
        "workflow",
        "multiple steps",
    ]

    async def classify(
        self, query: str, context: Optional[dict] = None
    ) -> TaskClassification:
        logger.info("llm.classify_task_start", query_len=len(query or ""))

        # If context has doc_ids, bypass heuristics and route directly to DOCUMENT
        if context and context.get("doc_ids"):
            logger.info(
                "llm.classify_document_override", doc_count=len(context["doc_ids"])
            )
            return TaskClassification(
                primary_agent=TaskType.DOCUMENT,
                confidence=1.0,
                reasoning="Query target explicitly specified documents via doc_ids.",
                requires_memory=False,
                requires_documents=True,
                estimated_complexity="medium",
            )

        # Handle empty/whitespace queries
        if not query or not query.strip():
            logger.info("llm.classify_empty_query_default")
            return TaskClassification(
                primary_agent=TaskType.RESEARCH,
                confidence=1.0,
                reasoning="Empty or whitespace query defaulted to RESEARCH.",
                requires_memory=False,
                requires_documents=False,
                estimated_complexity="low",
            )

        # 1. Direct heuristic scoring
        scores = {
            TaskType.RESEARCH: 0.1,  # base baseline score
            TaskType.CODE: 0.0,
            TaskType.DOCUMENT: 0.0,
            TaskType.WORKFLOW: 0.0,
            TaskType.MEMORY: 0.0,
        }

        query_lower = query.lower()

        # Code signals
        for sig in self.CODE_SIGNALS:
            if sig in query_lower or sig in query:
                scores[TaskType.CODE] += 0.5
        if "```" in query:
            scores[TaskType.CODE] += 1.0

        # Document signals
        for sig in self.DOCUMENT_SIGNALS:
            if sig in query_lower:
                scores[TaskType.DOCUMENT] += 0.6

        # Memory signals
        for sig in self.MEMORY_SIGNALS:
            if sig in query_lower:
                scores[TaskType.MEMORY] += 0.6

        # Workflow signals
        for sig in self.WORKFLOW_SIGNALS:
            if ".*" in sig:
                if re.search(sig, query_lower):
                    scores[TaskType.WORKFLOW] += 2.0
            else:
                if sig in query_lower:
                    scores[TaskType.WORKFLOW] += 1.8

        # Determine max category and score
        primary = max(scores, key=scores.get)
        confidence = min(scores[primary], 1.0)

        # If confidence is robust, return immediately
        if confidence >= 0.5:
            logger.info(
                "llm.classify_heuristic_success",
                primary=primary.value,
                confidence=confidence,
            )
            classification = TaskClassification(
                primary_agent=primary,
                secondary_agents=[
                    k for k, v in scores.items() if v > 0.2 and k != primary
                ],
                confidence=confidence,
                reasoning=f"Heuristic scoring chose {primary.value} based on direct signal matching.",
                requires_memory=scores[TaskType.MEMORY] > 0.2,
                requires_documents=scores[TaskType.DOCUMENT] > 0.2,
                estimated_complexity=(
                    "high"
                    if scores[TaskType.CODE] > 0.5 or scores[TaskType.WORKFLOW] > 0.4
                    else "medium"
                ),
            )
        else:
            # 2. Fallback to LLM Classification
            logger.info("llm.classify_fallback_to_llm", confidence=confidence)
            system_prompt = (
                "You are a routing classification assistant. Classify the user query into one of these types: "
                "RESEARCH, CODE, DOCUMENT, WORKFLOW, MEMORY.\n"
                "Format the output strictly as a valid JSON object with the following keys:\n"
                "- primary_agent: string in uppercase (must be one of: RESEARCH, CODE, DOCUMENT, WORKFLOW, MEMORY)\n"
                "- secondary_agents: list of uppercase strings\n"
                "- confidence: float between 0.0 and 1.0\n"
                "- reasoning: concise explanation string\n"
                "- requires_memory: boolean\n"
                "- requires_documents: boolean\n"
                "- estimated_complexity: string (low, medium, high)\n"
                "Do not include any wrapper tags, backticks, or other text outside the JSON."
            )

            try:
                import asyncio

                llm = get_llm_client()
                if llm._model is None:
                    await llm.initialize()

                # Add 10-second timeout to LLM call to prevent hangs
                res = await asyncio.wait_for(
                    llm.generate(
                        prompt=f"Classify this query: {query}",
                        system_prompt=system_prompt,
                    ),
                    timeout=10.0,
                )

                # Clean response text
                clean_text = res.text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()

                data = json.loads(clean_text)

                # Parse enum and fields dynamically
                primary_str = data.get("primary_agent", "RESEARCH").upper()
                try:
                    primary_agent = TaskType[primary_str]
                except KeyError:
                    primary_agent = TaskType.RESEARCH

                secondary_list = []
                for sec in data.get("secondary_agents", []):
                    try:
                        secondary_list.append(TaskType[sec.upper()])
                    except KeyError as e:
                        import logging
                        logging.getLogger(__name__).warning(f"Ignored error in KeyError: {e}")

                classification = TaskClassification(
                    primary_agent=primary_agent,
                    secondary_agents=secondary_list,
                    confidence=float(data.get("confidence", 0.7)),
                    reasoning=data.get("reasoning", "LLM determined selection."),
                    requires_memory=bool(data.get("requires_memory", False)),
                    requires_documents=bool(data.get("requires_documents", False)),
                    estimated_complexity=data.get("estimated_complexity", "medium"),
                )
            except Exception as e:
                logger.error("llm.classify_llm_failed", error=str(e))
                # Safe absolute fallback
                classification = TaskClassification(
                    primary_agent=TaskType.RESEARCH,
                    confidence=0.5,
                    reasoning="Classification fallback to RESEARCH due to LLM parsing/timeout exception.",
                    requires_memory=False,
                    requires_documents=False,
                    estimated_complexity="medium",
                )

        # Enforce that confidence < 0.3 always falls back to RESEARCH
        if classification.confidence < 0.3:
            logger.info(
                "llm.classify_low_confidence_fallback",
                confidence=classification.confidence,
            )
            classification.primary_agent = TaskType.RESEARCH
            classification.confidence = 0.5
            classification.reasoning = f"Redirected to RESEARCH: Classification confidence was too low ({classification.confidence})."

        return classification
