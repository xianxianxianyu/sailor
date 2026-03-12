from __future__ import annotations

import logging

from fastapi import APIRouter

from backend.app.container import AppContainer
from backend.app.schemas import (
    LLMSettingsOut,
    TestLLMOut,
    UpdateLLMSettingsIn,
    EmbeddingSettingsOut,
    UpdateEmbeddingSettingsIn,
)

logger = logging.getLogger(__name__)


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def mount_settings_routes(container: AppContainer) -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["system"])

    @router.get("/llm", response_model=LLMSettingsOut)
    def get_llm_settings():
        config = container.llm_config_engine.load_llm_config()
        return LLMSettingsOut(
            provider=config.provider,
            api_key_set=bool(config.api_key),
            api_key_preview=_mask_key(config.api_key),
            base_url=config.base_url,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    @router.put("/llm", response_model=LLMSettingsOut)
    def update_llm_settings(body: UpdateLLMSettingsIn):
        container.llm_config_engine.save_llm_config(
            provider=body.provider,
            base_url=body.base_url,
            model=body.model,
            api_key=body.api_key if body.api_key else None,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        container.llm_config_engine.reload_all()

        logger.info("LLM 配置已更新: provider=%s model=%s", body.provider, body.model)

        config = container.llm_config_engine.load_llm_config()
        return LLMSettingsOut(
            provider=config.provider,
            api_key_set=bool(config.api_key),
            api_key_preview=_mask_key(config.api_key),
            base_url=config.base_url,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    @router.post("/llm/test", response_model=TestLLMOut)
    def test_llm_connection():
        success, message = container.llm_config_engine.test_connection()
        return TestLLMOut(success=success, message=message)

    @router.get("/llm/status")
    def get_llm_status():
        """获取 LLM 状态和统计信息"""
        status = container.llm_config_engine.get_status()
        stats = container.llm_config_engine.get_stats()
        return {
            "config": status,
            "stats": stats,
        }

    @router.get("/embedding", response_model=EmbeddingSettingsOut)
    def get_embedding_settings():
        config = container.llm_config_engine.load_embedding_config()
        return EmbeddingSettingsOut(
            provider=config.provider,
            api_key_set=bool(config.api_key),
            api_key_preview=_mask_key(config.api_key),
            base_url=config.base_url,
            model=config.model,
            dimensions=config.dimensions,
        )

    @router.put("/embedding", response_model=EmbeddingSettingsOut)
    def update_embedding_settings(body: UpdateEmbeddingSettingsIn):
        container.llm_config_engine.save_embedding_config(
            provider=body.provider,
            base_url=body.base_url,
            model=body.model,
            api_key=body.api_key if body.api_key else None,
            dimensions=body.dimensions,
        )

        logger.info("Embedding 配置已更新: provider=%s model=%s", body.provider, body.model)

        config = container.llm_config_engine.load_embedding_config()
        return EmbeddingSettingsOut(
            provider=config.provider,
            api_key_set=bool(config.api_key),
            api_key_preview=_mask_key(config.api_key),
            base_url=config.base_url,
            model=config.model,
            dimensions=config.dimensions,
        )

    @router.get("/embedding/status")
    def get_embedding_status():
        """获取 Embedding 状态信息"""
        return container.llm_config_engine.get_embedding_status()

    return router
