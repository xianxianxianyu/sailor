"""FollowRepository - Follow data access layer

Provides CRUD operations for Follow configurations.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from core.follow.models import Follow
from core.storage.db import Database


class FollowRepository:
    """Follow data access layer"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create Follow tables and indexes"""
        with self.db.connect() as conn:
            # follows table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS follows (
                    follow_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NULL,
                    board_ids_json TEXT NULL,
                    research_program_ids_json TEXT NULL,
                    window_policy TEXT NOT NULL DEFAULT 'daily',
                    schedule_minutes INTEGER NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at TEXT NULL,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(name)
                )
            """)

            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_follows_enabled
                ON follows(enabled)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_follows_schedule
                ON follows(schedule_minutes, enabled)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_follows_last_run
                ON follows(last_run_at DESC)
            """)

            conn.commit()

    # ========== ID Generation ==========

    def _generate_follow_id(self, name: str) -> str:
        """Generate deterministic follow_id from name"""
        key = f"follow:{name}".encode("utf-8")
        hash_hex = hashlib.sha256(key).hexdigest()[:12]
        return f"follow_{hash_hex}"

    # ========== CRUD Operations ==========

    def upsert_follow(
        self,
        name: str,
        description: str | None = None,
        board_ids: list[str] | None = None,
        research_program_ids: list[str] | None = None,
        window_policy: str = "daily",
        schedule_minutes: int | None = None,
        enabled: bool = True,
    ) -> Follow:
        """Create or update a Follow"""
        follow_id = self._generate_follow_id(name)
        now = datetime.utcnow()

        board_ids_json = json.dumps(board_ids or [])
        research_program_ids_json = json.dumps(research_program_ids or [])

        with self.db.connect() as conn:
            # Check if exists
            row = conn.execute(
                "SELECT follow_id, created_at FROM follows WHERE follow_id = ?",
                (follow_id,),
            ).fetchone()

            if row:
                # Update existing
                conn.execute("""
                    UPDATE follows SET
                        name = ?,
                        description = ?,
                        board_ids_json = ?,
                        research_program_ids_json = ?,
                        window_policy = ?,
                        schedule_minutes = ?,
                        enabled = ?,
                        updated_at = ?
                    WHERE follow_id = ?
                """, (
                    name,
                    description,
                    board_ids_json,
                    research_program_ids_json,
                    window_policy,
                    schedule_minutes,
                    1 if enabled else 0,
                    now.isoformat(),
                    follow_id,
                ))
                created_at = datetime.fromisoformat(row[1])
            else:
                # Insert new
                conn.execute("""
                    INSERT INTO follows (
                        follow_id, name, description, board_ids_json,
                        research_program_ids_json, window_policy, schedule_minutes,
                        enabled, last_run_at, error_count, last_error,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, ?, ?)
                """, (
                    follow_id,
                    name,
                    description,
                    board_ids_json,
                    research_program_ids_json,
                    window_policy,
                    schedule_minutes,
                    1 if enabled else 0,
                    now.isoformat(),
                    now.isoformat(),
                ))
                created_at = now

            conn.commit()

        return self.get_follow(follow_id)  # type: ignore

    def get_follow(self, follow_id: str) -> Follow | None:
        """Get a single Follow by ID"""
        with self.db.connect() as conn:
            row = conn.execute("""
                SELECT follow_id, name, description, board_ids_json,
                       research_program_ids_json, window_policy, schedule_minutes,
                       enabled, last_run_at, error_count, last_error,
                       created_at, updated_at
                FROM follows
                WHERE follow_id = ?
            """, (follow_id,)).fetchone()

            if not row:
                return None

            return self._row_to_follow(row)

    def list_follows(
        self,
        enabled: bool | None = None,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Follow]:
        """List Follows with optional filters"""
        query = """
            SELECT follow_id, name, description, board_ids_json,
                   research_program_ids_json, window_policy, schedule_minutes,
                   enabled, last_run_at, error_count, last_error,
                   created_at, updated_at
            FROM follows
            WHERE 1=1
        """
        params: list[Any] = []

        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)
        elif enabled_only:
            query += " AND enabled = 1"

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_follow(row) for row in rows]

    def update_follow(self, follow_id: str, **updates: Any) -> Follow | None:
        """Partial update of a Follow"""
        if not updates:
            return self.get_follow(follow_id)

        # Build SET clause
        set_parts = []
        params = []

        for key, value in updates.items():
            if key in ("board_ids", "research_program_ids"):
                # JSON fields
                set_parts.append(f"{key}_json = ?")
                params.append(json.dumps(value))
            elif key == "enabled":
                set_parts.append("enabled = ?")
                params.append(1 if value else 0)
            elif key in ("name", "description", "window_policy", "schedule_minutes"):
                set_parts.append(f"{key} = ?")
                params.append(value)

        if not set_parts:
            return self.get_follow(follow_id)

        set_parts.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(follow_id)

        query = f"UPDATE follows SET {', '.join(set_parts)} WHERE follow_id = ?"

        with self.db.connect() as conn:
            conn.execute(query, params)
            conn.commit()

        return self.get_follow(follow_id)

    def delete_follow(self, follow_id: str) -> bool:
        """Delete a Follow"""
        with self.db.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM follows WHERE follow_id = ?",
                (follow_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_last_run(
        self,
        follow_id: str,
        timestamp: datetime,
        error: str | None = None,
    ) -> None:
        """Update last run status"""
        with self.db.connect() as conn:
            if error:
                conn.execute("""
                    UPDATE follows SET
                        last_run_at = ?,
                        error_count = error_count + 1,
                        last_error = ?,
                        updated_at = ?
                    WHERE follow_id = ?
                """, (timestamp.isoformat(), error, datetime.utcnow().isoformat(), follow_id))
            else:
                conn.execute("""
                    UPDATE follows SET
                        last_run_at = ?,
                        error_count = 0,
                        last_error = NULL,
                        updated_at = ?
                    WHERE follow_id = ?
                """, (timestamp.isoformat(), datetime.utcnow().isoformat(), follow_id))
            conn.commit()

    def list_scheduled_follows(self) -> list[Follow]:
        """Get Follows with schedule_minutes set and enabled"""
        with self.db.connect() as conn:
            rows = conn.execute("""
                SELECT follow_id, name, description, board_ids_json,
                       research_program_ids_json, window_policy, schedule_minutes,
                       enabled, last_run_at, error_count, last_error,
                       created_at, updated_at
                FROM follows
                WHERE enabled = 1 AND schedule_minutes IS NOT NULL
                ORDER BY last_run_at ASC NULLS FIRST
            """).fetchall()
            return [self._row_to_follow(row) for row in rows]

    # ========== Helper Methods ==========

    def _row_to_follow(self, row: Any) -> Follow:
        """Convert database row to Follow object"""
        return Follow(
            follow_id=row[0],
            name=row[1],
            description=row[2],
            board_ids=json.loads(row[3]) if row[3] else [],
            research_program_ids=json.loads(row[4]) if row[4] else [],
            window_policy=row[5],
            schedule_minutes=row[6],
            enabled=bool(row[7]),
            last_run_at=datetime.fromisoformat(row[8]) if row[8] else None,
            error_count=row[9],
            last_error=row[10],
            created_at=datetime.fromisoformat(row[11]) if row[11] else None,
            updated_at=datetime.fromisoformat(row[12]) if row[12] else None,
        )
