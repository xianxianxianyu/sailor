from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from urllib import error, parse, request

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1500


@dataclass(slots=True)
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str


class LLMClient:
    """使用 urllib 调用 OpenAI Chat Completions API，与 MinifluxCollector 风格一致。"""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def chat(self, messages: list[dict], temperature: float | None = None, max_tokens: int | None = None) -> LLMResponse:
        if not self.config.api_key:
            raise ValueError("OpenAI API Key 未配置")

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }

        endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
        )

        # 内置 1 次重试
        for attempt in range(2):
            try:
                with request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode("utf-8"))

                choice = result["choices"][0]
                usage = result.get("usage", {})

                return LLMResponse(
                    content=choice["message"]["content"],
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    model=result.get("model", self.config.model),
                )
            except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt == 0:
                    logger.warning("LLM 调用失败，重试中: %s", exc)
                    time.sleep(2)
                else:
                    raise
        raise RuntimeError("LLM 调用失败")
