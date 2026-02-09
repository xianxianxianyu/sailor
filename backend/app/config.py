from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    db_path: Path
    seed_file: Path
    miniflux_base_url: str
    miniflux_token: str
    cors_origins: list[str]


def load_settings(project_root: Path) -> Settings:
    cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    cors_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]

    return Settings(
        db_path=Path(os.getenv("SAILOR_DB_PATH", project_root / "data" / "sailor.db")),
        seed_file=Path(os.getenv("SAILOR_SEED_FILE", project_root / "data" / "seed_entries.json")),
        miniflux_base_url=os.getenv("MINIFLUX_BASE_URL", ""),
        miniflux_token=os.getenv("MINIFLUX_TOKEN", ""),
        cors_origins=cors_origins,
    )
