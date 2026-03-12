"""LLM Configuration Engine - Business logic layer."""

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import LLMConfig, EmbeddingConfig, ProviderType
from .repository import ConfigRepository
from .adapters import PROVIDER_ADAPTERS

if TYPE_CHECKING:
    from backend.app.container import AppContainer

logger = logging.getLogger(__name__)


class LLMConfigEngine:
    """Unified engine for LLM and Embedding configuration management."""

    def __init__(self, config_path: Path):
        self.repo = ConfigRepository(config_path)
        self._container: "AppContainer | None" = None
        self._call_stats = {
            "total_calls": 0,
            "total_tokens": 0,
            "last_call": None,
        }

    def set_container(self, container: "AppContainer") -> None:
        """Set container reference for hot reload."""
        self._container = container

    def load_llm_config(self) -> LLMConfig:
        """Load LLM configuration from JSON and keyring."""
        data = self.repo.read_json()
        llm_data = data.get("llm", {})
        # 兼容旧 keyring 账户名 "api_key"
        api_key = self.repo.read_keyring("llm_api_key") or self.repo.read_keyring("api_key")

        return LLMConfig(
            provider=llm_data.get("provider", "deepseek"),
            base_url=llm_data.get("base_url", "https://api.deepseek.com/v1"),
            model=llm_data.get("model", "deepseek-chat"),
            api_key=api_key,
            temperature=llm_data.get("temperature", 0.3),
            max_tokens=llm_data.get("max_tokens", 1500),
        )

    def load_embedding_config(self) -> EmbeddingConfig:
        """Load Embedding configuration from JSON and keyring."""
        data = self.repo.read_json()
        emb_data = data.get("embedding", {})
        api_key = self.repo.read_keyring("embedding_api_key")

        return EmbeddingConfig(
            provider=emb_data.get("provider", "qwen"),
            base_url=emb_data.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model=emb_data.get("model", "text-embedding-v3"),
            api_key=api_key,
            dimensions=emb_data.get("dimensions", 1024),
        )

    def save_llm_config(
        self,
        provider: ProviderType,
        base_url: str,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> None:
        """Save LLM configuration to JSON and keyring."""
        data = self.repo.read_json()
        data["llm"] = {
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        self.repo.write_json(data)

        if api_key:
            self.repo.write_keyring("llm_api_key", api_key)

    def save_embedding_config(
        self,
        provider: ProviderType,
        base_url: str,
        model: str,
        api_key: str | None = None,
        dimensions: int = 1536,
    ) -> None:
        """Save Embedding configuration to JSON and keyring."""
        data = self.repo.read_json()
        data["embedding"] = {
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "dimensions": dimensions,
        }
        self.repo.write_json(data)

        if api_key:
            self.repo.write_keyring("embedding_api_key", api_key)

    def create_llm_client(self):
        """Create LLMClient instance compatible with existing code."""
        config = self.load_llm_config()

        # Import here to avoid circular dependency
        from core.agent.base import LLMClient, LLMConfig as BaseLLMConfig

        base_config = BaseLLMConfig(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return LLMClient(base_config)

    def create_embedding_client(self):
        """Create EmbeddingClient instance."""
        from core.embedding import EmbeddingClient

        config = self.load_embedding_config()
        adapter = PROVIDER_ADAPTERS.get(config.provider)
        if not adapter:
            raise ValueError(f"Unknown embedding provider: {config.provider}")

        return EmbeddingClient(config, adapter)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """
        统一的 LLM 调用接口。

        Args:
            messages: 对话消息列表
            temperature: 温度参数（None 则使用配置值）
            max_tokens: 最大 token 数（None 则使用配置值）

        Returns:
            LLMResponse: 包含内容、模型、token 使用量
        """
        # 记录调用
        self._call_stats["total_calls"] += 1
        self._call_stats["last_call"] = datetime.now()

        logger.info(
            f"LLM call: messages={len(messages)}, temp={temperature}, max_tokens={max_tokens}"
        )

        try:
            # 加载配置
            config = self.load_llm_config()
            adapter = PROVIDER_ADAPTERS.get(config.provider)
            if not adapter:
                raise ValueError(f"Unknown provider: {config.provider}")

            # 调用 adapter
            result = adapter.chat(
                config=config,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # 转换为 LLMResponse（兼容现有代码）
            from core.agent.base import LLMResponse

            response = LLMResponse(
                content=result["choices"][0]["message"]["content"],
                model=result["model"],
                prompt_tokens=result["usage"]["prompt_tokens"],
                completion_tokens=result["usage"]["completion_tokens"],
            )

            # 统计 token
            total_tokens = response.prompt_tokens + response.completion_tokens
            self._call_stats["total_tokens"] += total_tokens

            logger.info(f"LLM response: model={response.model}, tokens={total_tokens}")

            return response

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def get_status(self) -> dict[str, Any]:
        """
        获取 LLM 状态信息。

        Returns:
            dict: 包含配置、连接状态等
        """
        config = self.load_llm_config()
        return {
            "provider": config.provider,
            "model": config.model,
            "base_url": config.base_url,
            "api_key_set": bool(config.api_key),
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }

    def get_embedding_status(self) -> dict[str, Any]:
        """获取 Embedding 状态信息。"""
        config = self.load_embedding_config()
        return {
            "provider": config.provider,
            "model": config.model,
            "base_url": config.base_url,
            "api_key_set": bool(config.api_key),
            "dimensions": config.dimensions,
        }

    def get_stats(self) -> dict[str, Any]:
        """
        获取调用统计信息。

        Returns:
            dict: 包含总调用次数、总 token 数、最后调用时间
        """
        return {
            "total_calls": self._call_stats["total_calls"],
            "total_tokens": self._call_stats["total_tokens"],
            "last_call": (
                self._call_stats["last_call"].isoformat()
                if self._call_stats["last_call"]
                else None
            ),
        }

    def test_connection(self) -> tuple[bool, str]:
        """Test LLM connection with a simple request."""
        try:
            messages = [{"role": "user", "content": "Hello"}]
            response = self.chat(messages, temperature=0.1, max_tokens=10)
            return True, f"Connection successful - model: {response.model}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def reload_all(self) -> None:
        """Hot reload all components that depend on LLM configuration."""
        if not self._container:
            return

        # Create new LLM client with Engine reference
        llm_client = self.create_llm_client()
        llm_client._engine = self  # 注入 Engine 引用
        self._container.llm_client = llm_client

        # Reload all agents
        from core.agent.article_agent import ArticleAnalysisAgent
        from core.agent.kb_agent import KBClusterAgent
        from core.agent.tagging_agent import TaggingAgent

        self._container.article_agent = ArticleAnalysisAgent(
            llm=llm_client,
            analysis_repo=self._container.analysis_repo,
            resource_repo=self._container.resource_repo,
            kb_repo=self._container.kb_repo,
        )
        self._container.kb_agent = KBClusterAgent(
            llm=llm_client,
            report_repo=self._container.report_repo,
            analysis_repo=self._container.analysis_repo,
            resource_repo=self._container.resource_repo,
            kb_repo=self._container.kb_repo,
        )
        self._container.tagging_agent = TaggingAgent(
            llm=llm_client,
            tag_repo=self._container.tag_repo,
        )

        # Reload engines
        from core.kg.link_engine import KGLinkEngine
        from core.engines.intelligence import ResourceIntelligenceEngine

        self._container.kg_link_engine = KGLinkEngine(llm=llm_client)
        self._container.intelligence_engine = ResourceIntelligenceEngine(
            resource_repo=self._container.resource_repo,
            tag_repo=self._container.tag_repo,
            analysis_repo=self._container.analysis_repo,
            tagging_agent=self._container.tagging_agent,
            article_agent=self._container.article_agent,
        )

        # Re-register handlers that use these engines
        from core.kg.handlers import KGAddNodeHandler, KGRelinkNodeHandler
        from core.runner.intelligence_handler import IntelligenceHandler

        self._container.job_runner.register(
            "kg_add_node",
            KGAddNodeHandler(
                kg_repo=self._container.kb_graph_repo,
                link_engine=self._container.kg_link_engine,
            ),
        )
        self._container.job_runner.register(
            "kg_relink_node",
            KGRelinkNodeHandler(
                kg_repo=self._container.kb_graph_repo,
                link_engine=self._container.kg_link_engine,
            ),
        )
        self._container.job_runner.register(
            "resource_intelligence_run",
            IntelligenceHandler(self._container.intelligence_engine),
        )
