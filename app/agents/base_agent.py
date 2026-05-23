from dataclasses import dataclass, field
from typing import List, Optional, ClassVar, Any
from abc import ABC, abstractmethod

@dataclass
class AgentContext:
    memories: List[dict] = field(default_factory=list)
    doc_chunks: List[dict] = field(default_factory=list)
    chat_history: List[dict] = field(default_factory=list)
    session_id: str = "default"
    user_id: Optional[str] = None

@dataclass
class AgentResult:
    response: str
    agent_type: str
    tokens_used: int
    latency_ms: int
    confidence: float = 1.0
    sources: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

class BaseAgent(ABC):
    agent_type: ClassVar[str]
    system_prompt: ClassVar[str]

    @abstractmethod
    async def execute(self, query: str, context: AgentContext, stream: bool = False) -> Any:
        """
        Execute agent task. 
        Returns AgentResult if stream=False, or AsyncGenerator[LLMStreamChunk, None] if stream=True.
        """
        pass

    def _build_context_section(self, context: AgentContext) -> str:
        """
        Builds doc_chunks and memories sections to embed in the prompt context.
        """
        sections = []
        
        # 1. Document chunks
        if context.doc_chunks:
            chunks_list = []
            for chunk in context.doc_chunks:
                if isinstance(chunk, dict):
                    text = chunk.get('text') or chunk.get('content') or str(chunk)
                else:
                    text = str(chunk)
                chunks_list.append(text)
            sections.append("DOCUMENT CHUNKS:\n" + "\n".join(chunks_list))
            
        # 2. Memories
        if context.memories:
            mems_list = []
            for mem in context.memories:
                if isinstance(mem, dict):
                    content = mem.get('content') or str(mem)
                else:
                    content = str(mem)
                mems_list.append(content)
            sections.append("RELEVANT MEMORIES:\n" + "\n".join(mems_list))
            
        return "\n\n".join(sections) + "\n\n" if sections else ""

    def _check_context_length(self, prompt: str, max_chars: int = 24000) -> str:
        """
        Truncate context to ensure safety limits under max_chars.
        """
        if len(prompt) > max_chars:
            return prompt[:max_chars] + "\n[TRUNCATED DUE TO CONTEXT LIMITS...]"
        return prompt
