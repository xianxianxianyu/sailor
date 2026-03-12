"""Provider adapters for LLM and Embedding APIs."""

import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from .models import LLMConfig, EmbeddingConfig


class ProviderAdapter(ABC):
    """Abstract base class for provider adapters."""

    @abstractmethod
    def chat(
        self,
        config: LLMConfig,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Send chat completion request."""
        pass

    @abstractmethod
    def embed(self, config: EmbeddingConfig, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts."""
        pass


class OpenAIAdapter(ProviderAdapter):
    """Adapter for OpenAI-compatible APIs (OpenAI, DeepSeek, Qwen, Local)."""

    def chat(
        self,
        config: LLMConfig,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Send chat completion request to OpenAI-compatible endpoint."""
        endpoint = f"{config.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else config.max_tokens,
        }
        return self._post_json(endpoint, payload, config.api_key)

    def embed(self, config: EmbeddingConfig, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI-compatible endpoint."""
        endpoint = f"{config.base_url.rstrip('/')}/embeddings"
        payload: dict[str, Any] = {
            "model": config.model,
            "input": texts,
        }
        if config.dimensions != 1536:
            payload["dimensions"] = config.dimensions

        result = self._post_json(endpoint, payload, config.api_key)
        return [item["embedding"] for item in result["data"]]

    def _post_json(self, url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        """Send POST request with JSON payload."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"HTTP {e.code}: {error_body}")
        except Exception as e:
            raise RuntimeError(f"Request failed: {str(e)}")


# Provider mapping
PROVIDER_ADAPTERS: dict[str, ProviderAdapter] = {
    "openai": OpenAIAdapter(),
    "deepseek": OpenAIAdapter(),
    "qwen": OpenAIAdapter(),
    "local": OpenAIAdapter(),
}
