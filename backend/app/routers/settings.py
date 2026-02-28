from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from backend.app.container import AppContainer
from backend.app.schemas import LLMSettingsOut, TestLLMOut, UpdateLLMSettingsIn

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "sailor-llm"
KEYRING_USERNAME = "api_key"


def _config_path(container: AppContainer) -> Path:
    return container.settings.db_path.parent / "llm_config.json"


def _load_config_file(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_config_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_api_key() -> str:
    try:
        import keyring
        key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        return key or ""
    except Exception:
        return ""


def _set_api_key(key: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key)
    except Exception as exc:
        logger.warning("keyring 存储 API Key 失败: %s", exc)


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def mount_settings_routes(container: AppContainer) -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])

    @router.get("/llm", response_model=LLMSettingsOut)
    def get_llm_settings():
        cfg = _load_config_file(_config_path(container))
        api_key = _get_api_key() or container.settings.openai_api_key
        return LLMSettingsOut(
            provider=cfg.get("provider", "deepseek"),
            api_key_set=bool(api_key),
            api_key_preview=_mask_key(api_key),
            base_url=cfg.get("base_url", container.settings.openai_base_url),
            model=cfg.get("model", container.settings.openai_model),
            temperature=cfg.get("temperature", 0.3),
            max_tokens=cfg.get("max_tokens", 1500),
        )

    @router.put("/llm", response_model=LLMSettingsOut)
    def update_llm_settings(body: UpdateLLMSettingsIn):
        if body.api_key:
            _set_api_key(body.api_key)
            resolved_key = body.api_key
        else:
            resolved_key = _get_api_key() or container.settings.openai_api_key

        _save_config_file(
            _config_path(container),
            {
                "provider": body.provider,
                "base_url": body.base_url,
                "model": body.model,
                "temperature": body.temperature,
                "max_tokens": body.max_tokens,
            },
        )

        container.reload_llm(
            api_key=resolved_key,
            base_url=body.base_url,
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )

        logger.info("LLM 配置已更新: provider=%s model=%s", body.provider, body.model)

        return LLMSettingsOut(
            provider=body.provider,
            api_key_set=bool(resolved_key),
            api_key_preview=_mask_key(resolved_key),
            base_url=body.base_url,
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )

    @router.post("/llm/test", response_model=TestLLMOut)
    def test_llm_connection():
        try:
            resp = container.llm_client.chat(
                messages=[{"role": "user", "content": "Reply with exactly the word: OK"}],
                max_tokens=10,
                temperature=0,
            )
            return TestLLMOut(success=True, message=f"连接成功 · 模型: {resp.model}")
        except ValueError as exc:
            return TestLLMOut(success=False, message=str(exc))
        except Exception as exc:
            return TestLLMOut(success=False, message=f"连接失败: {exc}")

    return router
