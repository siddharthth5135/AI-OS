import re
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class DocumentChunk:
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict = field(default_factory=dict)

class DocumentChunker:
    CHUNK_SIZE = 500
    OVERLAP = 100
    MIN_CHUNK = 50

    def chunk_text(self, text: str, metadata: Optional[dict] = None) -> List[DocumentChunk]:
        """
        Split a document string into overlapping chunks of CHUNK_SIZE characters.
        Aims to respect structural break points: paragraphs > sentences > spaces.
        """
        if not text:
            return []

        chunks: List[DocumentChunk] = []
        text_len = len(text)
        cursor = 0
        chunk_idx = 0

        while cursor < text_len:
            # If the remaining text is extremely small, wrap it as final chunk and break
            if text_len - cursor <= self.MIN_CHUNK and chunks:
                break
            
            # Determine end target boundary
            end_target = min(cursor + self.CHUNK_SIZE, text_len)
            
            # If we are not at the very end of the file, find the best break point near the target
            end = end_target
            if end < text_len:
                # Look backwards up to CHUNK_SIZE - MIN_CHUNK to find a nice break point
                search_window = text[end - 150:end + 1] # search +/- around end target
                
                # Try paragraph break
                para_match = [m.start() for m in re.finditer(r"\n\s*\n", search_window)]
                if para_match:
                    # use the last paragraph break in the window
                    end = (end - 150) + para_match[-1] + 2
                else:
                    # Try sentence break
                    sent_match = [m.start() for m in re.finditer(r"\.\s", search_window)]
                    if sent_match:
                        end = (end - 150) + sent_match[-1] + 2
                    else:
                        # Try space break
                        space_match = [m.start() for m in re.finditer(r"\s", search_window)]
                        if space_match:
                            end = (end - 150) + space_match[-1] + 1

            # Ensure we are always moving forward to prevent infinite loops
            if end <= cursor:
                end = end_target

            chunk_text = text[cursor:end].strip()
            
            if len(chunk_text) >= self.MIN_CHUNK or not chunks:
                chunks.append(DocumentChunk(
                    text=chunk_text,
                    chunk_index=chunk_idx,
                    start_char=cursor,
                    end_char=end,
                    metadata=metadata or {}
                ))
                chunk_idx += 1

            # Advance cursor with overlap
            cursor = max(end - self.OVERLAP, cursor + 1)

        return chunks
