from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Settings:
    db_path: Path
    seed_file: Path
    cors_origins: list[str]
    opml_file: Path


def load_settings(project_root: Path) -> Settings:
    cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    cors_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]

    settings = Settings(
        db_path=Path(os.getenv("SAILOR_DB_PATH", project_root / "data" / "sailor.db")),
        seed_file=Path(os.getenv("SAILOR_SEED_FILE", project_root / "data" / "seed_entries.json")),
        cors_origins=cors_origins,
        opml_file=Path(os.getenv("SAILOR_OPML_FILE", project_root / "1.md")),
    )

    # Log configuration summary
    logger.info("Configuration loaded:")
    logger.info(f"  DB path: {settings.db_path}")
    logger.info(f"  CORS origins: {settings.cors_origins}")

    return settings
