from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime

from core.models import ResourceTag, UserAction, UserTag
from core.storage.db import Database


class TagRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ── Tag CRUD ──

    def create_tag(self, name: str, color: str = "#0f766e") -> UserTag:
        tag_id = f"tag_{hashlib.sha1(name.encode()).hexdigest()[:8]}"
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO user_tags (tag_id, name, color) VALUES (?, ?, ?) ON CONFLICT(name) DO NOTHING",
                (tag_id, name, color),
            )
            row = conn.execute("SELECT * FROM user_tags WHERE name = ?", (name,)).fetchone()
        return self._row_to_tag(row)

    def list_tags(self) -> list[UserTag]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM user_tags ORDER BY weight DESC, name ASC").fetchall()
        return [self._row_to_tag(r) for r in rows]

    def get_tag(self, tag_id: str) -> UserTag | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM user_tags WHERE tag_id = ?", (tag_id,)).fetchone()
        return self._row_to_tag(row) if row else None

    def update_tag(self, tag_id: str, name: str | None = None, color: str | None = None) -> UserTag | None:
        sets, params = [], []
        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if color is not None:
            sets.append("color = ?")
            params.append(color)
        if not sets:
            return self.get_tag(tag_id)
        params.append(tag_id)
        with self.db.connect() as conn:
            conn.execute(f"UPDATE user_tags SET {', '.join(sets)} WHERE tag_id = ?", params)
            row = conn.execute("SELECT * FROM user_tags WHERE tag_id = ?", (tag_id,)).fetchone()
        return self._row_to_tag(row) if row else None

    def delete_tag(self, tag_id: str) -> bool:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM resource_tags WHERE tag_id = ?", (tag_id,))
            cursor = conn.execute("DELETE FROM user_tags WHERE tag_id = ?", (tag_id,))
        return cursor.rowcount > 0

    def increment_weight(self, tag_id: str, delta: int = 1) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE user_tags SET weight = weight + ? WHERE tag_id = ?", (delta, tag_id))

    # ── Resource-Tag 关联 ──

    def tag_resource(self, resource_id: str, tag_id: str, source: str = "auto") -> ResourceTag:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO resource_tags (resource_id, tag_id, source) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (resource_id, tag_id, source),
            )
            row = conn.execute(
                "SELECT * FROM resource_tags WHERE resource_id = ? AND tag_id = ?",
                (resource_id, tag_id),
            ).fetchone()
        return ResourceTag(
            resource_id=row["resource_id"],
            tag_id=row["tag_id"],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    def get_resource_tags(self, resource_id: str) -> list[UserTag]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT t.* FROM user_tags t
                   JOIN resource_tags rt ON t.tag_id = rt.tag_id
                   WHERE rt.resource_id = ?
                   ORDER BY t.name ASC""",
                (resource_id,),
            ).fetchall()
        return [self._row_to_tag(r) for r in rows]

    def get_resources_by_tag(self, tag_id: str) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT resource_id FROM resource_tags WHERE tag_id = ? ORDER BY created_at DESC",
                (tag_id,),
            ).fetchall()
        return [r["resource_id"] for r in rows]

    # ── User Actions 记录 ──

    def record_action(
        self,
        action_type: str,
        resource_id: str | None = None,
        tag_id: str | None = None,
        kb_id: str | None = None,
        metadata_json: str | None = None,
    ) -> UserAction:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """INSERT INTO user_actions (action_type, resource_id, tag_id, kb_id, metadata_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (action_type, resource_id, tag_id, kb_id, metadata_json),
            )
            row = conn.execute("SELECT * FROM user_actions WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._row_to_action(row)

    def list_actions(self, limit: int = 50) -> list[UserAction]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM user_actions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_action(r) for r in rows]

    # ── helpers ──

    @staticmethod
    def _row_to_tag(row: sqlite3.Row) -> UserTag:
        return UserTag(
            tag_id=row["tag_id"],
            name=row["name"],
            color=row["color"],
            weight=row["weight"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    @staticmethod
    def _row_to_action(row: sqlite3.Row) -> UserAction:
        return UserAction(
            id=row["id"],
            action_type=row["action_type"],
            resource_id=row["resource_id"],
            tag_id=row["tag_id"],
            kb_id=row["kb_id"],
            metadata_json=row["metadata_json"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )
