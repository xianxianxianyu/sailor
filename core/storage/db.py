from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS resources (
                    resource_id TEXT PRIMARY KEY,
                    canonical_url TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    title TEXT NOT NULL,
                    published_at TEXT,
                    text TEXT NOT NULL,
                    original_url TEXT NOT NULL,
                    topics_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    kb_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT
                );

                CREATE TABLE IF NOT EXISTS kb_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kb_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(kb_id, resource_id),
                    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(kb_id),
                    FOREIGN KEY(resource_id) REFERENCES resources(resource_id)
                );
                """
            )
