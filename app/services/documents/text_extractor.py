import re
import fitz  # PyMuPDF
import chardet
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExtractedDocument:
    full_text: str
    page_count: int
    word_count: int
    is_scanned: bool = False

class TextExtractor:
    def _clean_text(self, text: str) -> str:
        """
        Clean raw text: remove null bytes and normalize whitespace.
        """
        if not text:
            return ""
        # Remove null bytes
        text = text.replace("\x00", "")
        # Normalize whitespace (replace multiple spaces/tabs/newlines with a single space or newline)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()

    async def extract(self, path: str, file_type: str) -> ExtractedDocument:
        """
        Dispatches file text extraction based on file extension / type.
        """
        f_type = file_type.lower().strip(".")
        if f_type == "pdf":
            return await self.extract_pdf(path)
        elif f_type in ["txt", "text"]:
            return await self.extract_txt(path)
        elif f_type == "md":
            return await self.extract_md(path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    async def extract_pdf(self, path: str) -> ExtractedDocument:
        """
        Extract text page-by-page from PDF. Detects if it is a scanned document (density < 50 chars/page).
        """
        import asyncio

        def _sync_extract_pdf():
            doc = fitz.open(path)
            if doc.is_encrypted:
                raise ValueError("PDF is encrypted. Decryption or password is required to parse.")
            pages_text = []
            page_count = len(doc)
            
            for page in doc:
                text = page.get_text() or ""
                pages_text.append(text)
            
            full_text = "\n".join(pages_text)
            cleaned_text = self._clean_text(full_text)
            
            # Scanned detection: if characters per page is less than 50
            total_chars = len(cleaned_text)
            avg_chars = total_chars / page_count if page_count > 0 else 0
            is_scanned = avg_chars < 50
            
            word_count = len(cleaned_text.split())
            
            return ExtractedDocument(
                full_text=cleaned_text,
                page_count=page_count,
                word_count=word_count,
                is_scanned=is_scanned
            )

        return await asyncio.to_thread(_sync_extract_pdf)

    async def extract_txt(self, path: str) -> ExtractedDocument:
        """
        Extract and decode TXT file content using chardet encoding detection.
        """
        import asyncio

        def _sync_extract_txt():
            # First read a chunk to detect encoding
            with open(path, "rb") as f:
                raw_data = f.read(10000)
            
            result = chardet.detect(raw_data)
            encoding = result.get("encoding") or "utf-8"

            # Read full content with detected encoding
            with open(path, "r", encoding=encoding, errors="ignore") as f:
                text = f.read()

            cleaned_text = self._clean_text(text)
            word_count = len(cleaned_text.split())

            return ExtractedDocument(
                full_text=cleaned_text,
                page_count=1,
                word_count=word_count,
                is_scanned=False
            )

        return await asyncio.to_thread(_sync_extract_txt)

    async def extract_md(self, path: str) -> ExtractedDocument:
        """
        Extract Markdown text content.
        """
        # Markdown matches text extraction perfectly
        return await self.extract_txt(path)
