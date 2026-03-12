"""Data models for LLM and Embedding configuration."""

from dataclasses import dataclass
from typing import Literal

ProviderType = Literal["openai", "deepseek", "qwen", "local"]


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    provider: ProviderType
    base_url: str
    model: str
    api_key: str
    temperature: float = 0.3
    max_tokens: int = 1500


@dataclass
class EmbeddingConfig:
    """Configuration for Embedding provider."""
    provider: ProviderType
    base_url: str
    model: str
    api_key: str
    dimensions: int = 1536
