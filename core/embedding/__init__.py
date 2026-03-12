"""Embedding client for generating text embeddings."""

from core.llm_config.models import EmbeddingConfig
from core.llm_config.adapters import ProviderAdapter


class EmbeddingClient:
    """Client for generating text embeddings using configured provider."""

    def __init__(self, config: EmbeddingConfig, adapter: ProviderAdapter):
        self.config = config
        self.adapter = adapter

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts with automatic batching."""
        if not texts:
            return []

        batch_size = 100
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self.adapter.embed(self.config, batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

