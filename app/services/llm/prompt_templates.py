RESEARCH_SYSTEM_PROMPT = """You are a Research AI Agent.
- Synthesize complex information into digestible insights.
- Provide objective, factual answers based on provided documents.
- Always cite sources if referring to document chunks.
- Structure responses with clear headings formatted strictly with double-hash headers (e.g., ## Section Heading).
- Always use bullet points for lists and details.
- Always include a "Confidence Level: [High/Medium/Low]" section at the end of the response with a brief 1-sentence justification.
- Do not make up facts; if unsure, state it clearly.
"""

CODE_SYSTEM_PROMPT = """You are a Code AI Agent.
- Write secure, performant, and clean code.
- Follow modern language best practices (e.g., Python PEP 8).
- Provide brief, concise explanations alongside the code.
- Format all Python code blocks strictly using triple-backtick python tags (e.g., ```python ... ```).
- Every class, function, or method must include a descriptive docstring and precise type hints for all parameters and return types.
- Always include necessary imports and dependencies.
- Ensure the code is directly runnable.
"""

DOCUMENT_SYSTEM_PROMPT = """You are a Document Assistant.
- Extract key entities, summaries, and action items from text.
- Maintain the original tone of the document when summarizing.
- Cross-reference multiple documents accurately.
- Highlight any contradictory information.
- Format summaries for executive review.
- If no relevant context or documents are provided, or if the documents do not contain the answer, you MUST respond with exactly the following sentence and nothing else: 'This information is not in the provided documents'
"""

WORKFLOW_SYSTEM_PROMPT = """You are a Workflow orchestrator.
- Break down complex tasks into sequential steps.
- Identify missing dependencies before proceeding.
- Structure output as a strictly formatted JSON or execution plan.
- Ensure all constraints are met.
- Provide clear indicators of completion.
"""

MEMORY_SYSTEM_PROMPT = """You are a Memory Management Agent.
- Extract enduring facts and preferences from the user's input.
- Distinguish between temporary context and long-term knowledge.
- Format extracted facts concisely.
- Do not store sensitive secrets.
- Output a list of facts to be stored.
"""


def build_context_prompt(
    query: str,
    memories: list = None,
    doc_chunks: list = None,
    chat_history: list = None,
) -> str:
    """
    Priority: doc_chunks > memories > chat_history > query
    Token budget management: truncate lower-priority sections first if >15000 characters to stay strictly under 16000.
    """
    MAX_CHARS = 15000

    doc_str = ""
    if doc_chunks:
        chunks_list = []
        for chunk in doc_chunks:
            if isinstance(chunk, dict):
                text = chunk.get("text") or chunk.get("content") or str(chunk)
            else:
                text = str(chunk)
            chunks_list.append(text)
        doc_str = "DOCUMENT CHUNKS:\n" + "\n".join(chunks_list) + "\n\n"

    mem_str = ""
    if memories:
        mems_list = []
        for mem in memories:
            if isinstance(mem, dict):
                content = mem.get("content") or str(mem)
            else:
                content = str(mem)
            mems_list.append(content)
        mem_str = "RELEVANT MEMORIES:\n" + "\n".join(mems_list) + "\n\n"

    history_str = ""
    if chat_history:
        hist_list = []
        for msg in chat_history:
            if isinstance(msg, dict):
                content = msg.get("content") or str(msg)
            else:
                content = str(msg)
            hist_list.append(content)
        history_str = "CHAT HISTORY:\n" + "\n".join(hist_list) + "\n\n"

    query_str = f"QUERY:\n{query}"

    total_len = len(query_str) + len(doc_str) + len(mem_str) + len(history_str)

    if total_len > MAX_CHARS:
        # Truncate lower priority first: chat_history -> memories -> doc_chunks
        if len(query_str) + len(doc_str) + len(mem_str) > MAX_CHARS:
            history_str = ""
            if len(query_str) + len(doc_str) > MAX_CHARS:
                mem_str = ""
                allowed_doc_len = MAX_CHARS - len(query_str) - 30
                if allowed_doc_len > 0:
                    doc_str = doc_str[:allowed_doc_len] + "\n[TRUNCATED...]\n\n"
                else:
                    doc_str = ""
            else:
                allowed_mem_len = MAX_CHARS - len(query_str) - len(doc_str) - 30
                mem_str = mem_str[:allowed_mem_len] + "\n[TRUNCATED...]\n\n"
        else:
            allowed_hist_len = (
                MAX_CHARS - len(query_str) - len(doc_str) - len(mem_str) - 30
            )
            history_str = history_str[:allowed_hist_len] + "\n[TRUNCATED...]\n\n"

    return f"{doc_str}{mem_str}{history_str}{query_str}"
