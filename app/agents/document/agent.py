import time
from typing import Any, List
from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.services.llm.gemini_client import get_llm_client
from app.services.llm.prompt_templates import DOCUMENT_SYSTEM_PROMPT

class DocumentAgent(BaseAgent):
    agent_type = "document"
    system_prompt = DOCUMENT_SYSTEM_PROMPT

    async def execute(
        self, 
        query: str, 
        context: AgentContext, 
        stream: bool = False, 
        **kwargs
    ) -> Any:
        llm = get_llm_client()

        # If no document chunks are present in context, abort immediately
        if not context.doc_chunks:
            error_response = "No documents. Upload first."
            if stream:
                # Return a simple mock stream yielding the error
                from app.services.llm.gemini_client import LLMStreamChunk
                async def mock_stream():
                    yield LLMStreamChunk(text=error_response, is_final=False)
                    yield LLMStreamChunk(text="", is_final=True, total_tokens=0, finish_reason="stop")
                return mock_stream()
            
            return AgentResult(
                response=error_response,
                agent_type=self.agent_type,
                tokens_used=0,
                latency_ms=0,
                confidence=0.0
            )

        # 1. Format structural reference sources
        sources_text_list = []
        sources_meta = []
        
        for idx, chunk in enumerate(context.doc_chunks):
            filename = chunk.get("original_filename") or chunk.get("filename") or f"Doc_{idx + 1}"
            text = chunk.get("text") or chunk.get("content") or ""
            
            sources_text_list.append(f"[Source {idx + 1} - {filename}]:\n{text}")
            
            # Preview of source content for front-end presentation
            sources_meta.append({
                "filename": filename,
                "text_preview": text[:200] + "..." if len(text) > 200 else text
            })

        sources_text = "\n\n".join(sources_text_list)
        
        # 2. Build constrained prompt
        prompt = (
            f"Sources:\n{sources_text}\n\n"
            f"Question: {query}\n\n"
            f"Answer ONLY from the provided sources. Do not utilize any external or pre-trained knowledge."
        )
        prompt = self._check_context_length(prompt)

        # 3. Stream execution
        if stream:
            return llm.generate_stream(prompt, system_prompt=self.system_prompt)

        # 4. Synchronous execution
        start_time = time.time()
        response = await llm.generate(prompt, system_prompt=self.system_prompt)
        elapsed = int((time.time() - start_time) * 1000)

        # Extract confidence
        confidence = 0.95 if context.doc_chunks else 0.5

        return AgentResult(
            response=response.text,
            agent_type=self.agent_type,
            tokens_used=response.total_tokens or 0,
            latency_ms=elapsed,
            confidence=confidence,
            sources=sources_meta
        )
