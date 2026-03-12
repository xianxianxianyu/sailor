"""Configuration persistence layer for LLM settings."""

import json
from pathlib import Path
from typing import Any


class ConfigRepository:
    """Handles reading and writing LLM configuration to disk and keyring."""

    def __init__(self, config_path: Path):
        self.config_path = config_path

    def read_json(self) -> dict[str, Any]:
        """Read configuration from JSON file, return default if not exists."""
        if not self.config_path.exists():
            return self._default_config()
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._default_config()

    def write_json(self, data: dict[str, Any]) -> None:
        """Write configuration to JSON file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def read_keyring(self, account: str) -> str:
        """Read API key from system keyring."""
        try:
            import keyring
            return keyring.get_password("sailor-llm", account) or ""
        except Exception:
            return ""

    def write_keyring(self, account: str, value: str) -> None:
        """Write API key to system keyring."""
        try:
            import keyring
            keyring.set_password("sailor-llm", account, value)
        except Exception:
            pass

    def _default_config(self) -> dict[str, Any]:
        """Return default configuration structure."""
        return {
            "version": "1.0",
            "llm": {
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "temperature": 0.3,
                "max_tokens": 1500
            },
            "embedding": {
                "provider": "qwen",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "text-embedding-v3",
                "dimensions": 1024
            }
        }
