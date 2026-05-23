from typing import List, Optional

def build_research_prompt(
    query: str, 
    memories: List[dict], 
    doc_chunks: List[dict], 
    chat_history: List[dict], 
    max_tokens: int = 4000
) -> str:
    """
    Builds a structured prompt within a strict token budget.
    Priority order with budget allocations:
    1. doc_chunks (60%)
    2. memories (20%)
    3. chat_history (15%)
    4. query (5%)
    
    Leftover characters are not rolled over but standard limits are enforced.
    Approximation: 1 token ≈ 4 characters.
    """
    total_chars_budget = max_tokens * 4
    
    docs_budget = int(total_chars_budget * 0.60)
    memories_budget = int(total_chars_budget * 0.20)
    history_budget = int(total_chars_budget * 0.15)
    query_budget = int(total_chars_budget * 0.05)
    
    # Process Query
    query_str = query or ""
    if len(query_str) > query_budget:
        query_str = query_str[:query_budget] + "\n[QUERY TRUNCATED due to budget limit]"
        
    # Process Docs
    docs_str = ""
    if doc_chunks:
        doc_texts = []
        for chunk in doc_chunks:
            if isinstance(chunk, dict):
                text = chunk.get("text") or chunk.get("content") or str(chunk)
            else:
                text = str(chunk)
            doc_texts.append(text)
        
        full_docs = "\n\n".join(doc_texts)
        if len(full_docs) > docs_budget:
            full_docs = full_docs[:docs_budget] + "\n[DOCUMENT CONTEXT TRUNCATED due to budget limit]"
        docs_str = f"DOCUMENT CONTEXT:\n{full_docs}"
        
    # Process Memories
    mems_str = ""
    if memories:
        mem_texts = []
        for mem in memories:
            if isinstance(mem, dict):
                text = mem.get("content") or mem.get("text") or str(mem)
            else:
                text = str(mem)
            mem_texts.append(text)
        
        full_mems = "\n\n".join(mem_texts)
        if len(full_mems) > memories_budget:
            full_mems = full_mems[:memories_budget] + "\n[MEMORIES TRUNCATED due to budget limit]"
        mems_str = f"RELEVANT MEMORIES:\n{full_mems}"
        
    # Process Chat History
    history_str = ""
    if chat_history:
        history_lines = []
        for msg in chat_history:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content") or msg.get("text") or ""
                history_lines.append(f"{role.upper()}: {content}")
            else:
                history_lines.append(str(msg))
        
        full_history = "\n".join(history_lines)
        if len(full_history) > history_budget:
            full_history = full_history[-history_budget:]  # keep most recent lines within budget
            full_history = "[CHAT HISTORY TRUNCATED...]\n" + full_history
        history_str = f"CHAT HISTORY:\n{full_history}"
        
    # Combine sections with clear separation
    sections = []
    if docs_str:
        sections.append(docs_str)
    if mems_str:
        sections.append(mems_str)
    if history_str:
        sections.append(history_str)
    if query_str:
        sections.append(f"QUERY:\n{query_str}")
        
    return "\n\n---\n\n".join(sections)
