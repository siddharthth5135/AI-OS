import asyncio
from typing import List

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    MODEL_NAME = "all-MiniLM-L6-v2"
    DIM = 384

    def __init__(self):
        self._model = None

    async def initialize(self):
        """
        Load SentenceTransformer model on CPU asynchronously using a background thread.
        """
        if self._model is None:
            self._model = await asyncio.to_thread(
                SentenceTransformer, self.MODEL_NAME, device="cpu"
            )

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text chunk.
        """
        if self._model is None:
            await self.initialize()

        # sentence-transformers encode returns numpy array, convert to list of floats
        embedding = await asyncio.to_thread(
            self._model.encode, text, normalize_embeddings=True
        )
        return embedding.tolist()

    async def embed_batch(
        self, texts: List[str], batch_size: int = 32
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of text chunks.
        """
        if self._model is None:
            await self.initialize()

        embeddings = await asyncio.to_thread(
            self._model.encode, texts, batch_size=batch_size, normalize_embeddings=True
        )
        return embeddings.tolist()

    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query using the recommended instruction prefix.
        """
        return await self.embed_text(f"query: {query}")


_embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    return _embedding_service
