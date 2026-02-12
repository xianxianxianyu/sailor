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

                CREATE TABLE IF NOT EXISTS rss_feeds (
                    feed_id         TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    xml_url         TEXT NOT NULL UNIQUE,
                    html_url        TEXT,
                    enabled         INTEGER NOT NULL DEFAULT 1,
                    last_fetched_at TEXT,
                    error_count     INTEGER DEFAULT 0,
                    last_error      TEXT,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS resource_analyses (
                    resource_id         TEXT PRIMARY KEY,
                    summary             TEXT NOT NULL,
                    topics_json         TEXT NOT NULL,
                    scores_json         TEXT NOT NULL,
                    kb_recommendations_json TEXT NOT NULL,
                    insights_json       TEXT NOT NULL,
                    model               TEXT NOT NULL,
                    prompt_tokens       INTEGER DEFAULT 0,
                    completion_tokens   INTEGER DEFAULT 0,
                    status              TEXT NOT NULL DEFAULT 'pending',
                    error_message       TEXT,
                    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at        TEXT,
                    FOREIGN KEY(resource_id) REFERENCES resources(resource_id)
                );

                CREATE TABLE IF NOT EXISTS kb_reports (
                    report_id       TEXT PRIMARY KEY,
                    kb_id           TEXT NOT NULL,
                    report_type     TEXT NOT NULL,
                    content_json    TEXT NOT NULL,
                    resource_count  INTEGER NOT NULL,
                    model           TEXT NOT NULL,
                    prompt_tokens   INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    error_message   TEXT,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at    TEXT,
                    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(kb_id)
                );

                CREATE TABLE IF NOT EXISTS user_tags (
                    tag_id      TEXT PRIMARY KEY,
                    name        TEXT NOT NULL UNIQUE,
                    color       TEXT DEFAULT '#0f766e',
                    weight      INTEGER DEFAULT 1,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_actions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    resource_id TEXT,
                    tag_id      TEXT,
                    kb_id       TEXT,
                    metadata_json TEXT,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(resource_id) REFERENCES resources(resource_id),
                    FOREIGN KEY(tag_id) REFERENCES user_tags(tag_id),
                    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(kb_id)
                );

                CREATE TABLE IF NOT EXISTS resource_tags (
                    resource_id TEXT NOT NULL,
                    tag_id      TEXT NOT NULL,
                    source      TEXT NOT NULL DEFAULT 'auto',
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(resource_id, tag_id),
                    FOREIGN KEY(resource_id) REFERENCES resources(resource_id),
                    FOREIGN KEY(tag_id) REFERENCES user_tags(tag_id)
                );
                """
            )
