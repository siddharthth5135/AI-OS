import json
import time
from typing import Any, List

from app.agents.base_agent import AgentContext, AgentResult, BaseAgent
from app.agents.research.prompt_builder import build_research_prompt
from app.services.llm.gemini_client import get_llm_client
from app.services.llm.prompt_templates import RESEARCH_SYSTEM_PROMPT


class ResearchAgent(BaseAgent):
    agent_type = "research"
    system_prompt = RESEARCH_SYSTEM_PROMPT

    async def execute(
        self, query: str, context: AgentContext, stream: bool = False
    ) -> Any:
        llm = get_llm_client()
        prompt = build_research_prompt(
            query=query,
            memories=context.memories,
            doc_chunks=context.doc_chunks,
            chat_history=context.chat_history,
            max_tokens=4000,
        )
        prompt = self._check_context_length(prompt)

        if stream:
            return llm.generate_stream(prompt, system_prompt=self.system_prompt)

        start_time = time.time()
        response = await llm.generate(prompt, system_prompt=self.system_prompt)
        elapsed = int((time.time() - start_time) * 1000)

        confidence = 0.9 if (context.doc_chunks or context.memories) else 0.7

        return AgentResult(
            response=response.text,
            agent_type=self.agent_type,
            tokens_used=response.total_tokens or 0,
            latency_ms=elapsed,
            confidence=confidence,
            sources=self._extract_sources(context),
        )

    def _extract_sources(self, context: AgentContext) -> List[str]:
        sources = []

        # Doc chunks sources
        for chunk in context.doc_chunks:
            if isinstance(chunk, dict):
                filename = (
                    chunk.get("filename")
                    or chunk.get("title")
                    or chunk.get("metadata", {}).get("filename")
                    or "Unknown Document"
                )
                preview = chunk.get("text") or chunk.get("content") or ""
                preview_snippet = (
                    (preview[:100] + "...") if len(preview) > 100 else preview
                )
                sources.append(
                    json.dumps(
                        {
                            "type": "document",
                            "filename": filename,
                            "preview": preview_snippet,
                        }
                    )
                )
            else:
                sources.append(
                    json.dumps(
                        {
                            "type": "document",
                            "filename": "Unknown Document",
                            "preview": str(chunk)[:100],
                        }
                    )
                )

        # Memories sources
        for mem in context.memories:
            if isinstance(mem, dict):
                preview = mem.get("content") or mem.get("text") or ""
                preview_snippet = (
                    (preview[:100] + "...") if len(preview) > 100 else preview
                )
                sources.append(
                    json.dumps(
                        {
                            "type": "memory",
                            "filename": "Session Memory",
                            "preview": preview_snippet,
                        }
                    )
                )
            else:
                sources.append(
                    json.dumps(
                        {
                            "type": "memory",
                            "filename": "Session Memory",
                            "preview": str(mem)[:100],
                        }
                    )
                )

        return sources
