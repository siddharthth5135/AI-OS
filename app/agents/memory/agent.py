import time
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.services.llm.gemini_client import get_llm_client
from app.services.llm.prompt_templates import MEMORY_SYSTEM_PROMPT
from app.services.llm.schemas import LLMStreamChunk

class MemoryAgent(BaseAgent):
    agent_type = "memory"
    system_prompt = MEMORY_SYSTEM_PROMPT

    async def execute(self, query: str, context: AgentContext, stream: bool = False) -> Any:
        """
        Execute memory summary/recall operations.
        If context has no memories, returns a default not found message.
        Otherwise, builds a context block and asks LLM to summarize from the memories.
        """
        if not context.memories:
            if stream:
                async def empty_generator():
                    yield LLMStreamChunk(text="No relevant memories found.", is_final=False)
                    yield LLMStreamChunk(text="", is_final=True, total_tokens=0, finish_reason="stop")
                return empty_generator()
            return AgentResult(
                response="No relevant memories found.",
                agent_type=self.agent_type,
                tokens_used=0,
                latency_ms=0,
                confidence=1.0
            )

        # Format memories: join [{type}] {content} for each memory
        mem_items = []
        for mem in context.memories:
            m_type = mem.get("memory_type") or mem.get("type") or "fact"
            content = mem.get("content") or mem.get("text") or str(mem)
            mem_items.append(f"[{m_type}] {content}")
            
        mem_text = "\n".join(mem_items)
        prompt = f"Memories:\n{mem_text}\n\nQuestion: {query}\n\nSummarize from memories."

        llm = get_llm_client()
        if stream:
            return llm.generate_stream(prompt, system_prompt=self.system_prompt)

        start_time = time.time()
        response = await llm.generate(prompt, system_prompt=self.system_prompt)
        elapsed = int((time.time() - start_time) * 1000)

        return AgentResult(
            response=response.text,
            agent_type=self.agent_type,
            tokens_used=response.total_tokens or 0,
            latency_ms=elapsed,
            confidence=0.9,
            sources=[str(mem) for mem in context.memories]
        )
