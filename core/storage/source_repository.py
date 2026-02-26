from __future__ import annotations

import json
import uuid
from datetime import datetime

from core.models import SourceRecord, SourceResourceRow, SourceRunLog
from core.storage.db import Database


class SourceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_sources(self, source_type: str | None = None, enabled_only: bool = False) -> list[SourceRecord]:
        query = "SELECT * FROM source_registry"
        where: list[str] = []
        params: list[object] = []

        if source_type:
            where.append("source_type = ?")
            params.append(source_type)
        if enabled_only:
            where.append("enabled = 1")

        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY source_type ASC, name ASC"

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_source(row) for row in rows]

    def get_source(self, source_id: str) -> SourceRecord | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM source_registry WHERE source_id = ?", (source_id,)).fetchone()
        return _row_to_source(row) if row else None

    def upsert_source(self, source: SourceRecord) -> SourceRecord:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_registry (
                    source_id,
                    source_type,
                    name,
                    endpoint,
                    config_json,
                    enabled,
                    schedule_minutes,
                    last_run_at,
                    error_count,
                    last_error,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source_id)
                DO UPDATE SET
                    source_type = excluded.source_type,
                    name = excluded.name,
                    endpoint = excluded.endpoint,
                    config_json = excluded.config_json,
                    enabled = excluded.enabled,
                    schedule_minutes = excluded.schedule_minutes,
                    last_run_at = excluded.last_run_at,
                    error_count = excluded.error_count,
                    last_error = excluded.last_error,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    source.source_id,
                    source.source_type,
                    source.name,
                    source.endpoint,
                    json.dumps(source.config),
                    1 if source.enabled else 0,
                    source.schedule_minutes,
                    source.last_run_at.isoformat() if source.last_run_at else None,
                    source.error_count,
                    source.last_error,
                ),
            )
            row = conn.execute("SELECT * FROM source_registry WHERE source_id = ?", (source.source_id,)).fetchone()
        return _row_to_source(row)

    def update_source(
        self,
        source_id: str,
        *,
        name: str | None = None,
        endpoint: str | None = None,
        config: dict | None = None,
        enabled: bool | None = None,
        schedule_minutes: int | None = None,
    ) -> SourceRecord | None:
        updates: list[str] = []
        params: list[object] = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if endpoint is not None:
            updates.append("endpoint = ?")
            params.append(endpoint)
        if config is not None:
            updates.append("config_json = ?")
            params.append(json.dumps(config))
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        if schedule_minutes is not None:
            updates.append("schedule_minutes = ?")
            params.append(schedule_minutes)

        if not updates:
            return self.get_source(source_id)

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(source_id)

        with self.db.connect() as conn:
            conn.execute(f"UPDATE source_registry SET {', '.join(updates)} WHERE source_id = ?", params)
            row = conn.execute("SELECT * FROM source_registry WHERE source_id = ?", (source_id,)).fetchone()

        return _row_to_source(row) if row else None

    def delete_source(self, source_id: str) -> bool:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM source_item_index WHERE source_id = ?", (source_id,))
            conn.execute("DELETE FROM source_run_log WHERE source_id = ?", (source_id,))
            cursor = conn.execute("DELETE FROM source_registry WHERE source_id = ?", (source_id,))
        return cursor.rowcount > 0

    def create_run(self, source_id: str) -> SourceRunLog:
        run_id = "run_" + uuid.uuid4().hex[:12]
        started_at = datetime.utcnow()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_run_log (
                    run_id,
                    source_id,
                    started_at,
                    status,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, source_id, started_at.isoformat(), "running", "{}"),
            )
        return SourceRunLog(run_id=run_id, source_id=source_id, started_at=started_at)

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        fetched_count: int,
        processed_count: int,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        finished_at = datetime.utcnow()
        with self.db.connect() as conn:
            row = conn.execute("SELECT source_id FROM source_run_log WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return
            source_id = row["source_id"]

            conn.execute(
                """
                UPDATE source_run_log
                SET finished_at = ?,
                    status = ?,
                    fetched_count = ?,
                    processed_count = ?,
                    error_message = ?,
                    metadata_json = ?
                WHERE run_id = ?
                """,
                (
                    finished_at.isoformat(),
                    status,
                    fetched_count,
                    processed_count,
                    error_message,
                    json.dumps(metadata or {}),
                    run_id,
                ),
            )

            if status == "success":
                conn.execute(
                    """
                    UPDATE source_registry
                    SET last_run_at = ?,
                        error_count = 0,
                        last_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_id = ?
                    """,
                    (finished_at.isoformat(), source_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE source_registry
                    SET last_run_at = ?,
                        error_count = error_count + 1,
                        last_error = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_id = ?
                    """,
                    (finished_at.isoformat(), error_message, source_id),
                )

    def list_runs(self, source_id: str, limit: int = 20) -> list[SourceRunLog]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM source_run_log
                WHERE source_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (source_id, limit),
            ).fetchall()
        return [_row_to_run(row) for row in rows]

    def upsert_item_index(self, source_id: str, item_key: str, canonical_url: str, resource_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_item_index (source_id, item_key, canonical_url, resource_id, last_seen_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source_id, item_key)
                DO UPDATE SET
                    canonical_url = excluded.canonical_url,
                    resource_id = excluded.resource_id,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (source_id, item_key, canonical_url, resource_id),
            )

    def get_status_summary(self) -> dict[str, object]:
        with self.db.connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS cnt FROM source_registry").fetchone()["cnt"]
            enabled = conn.execute("SELECT COUNT(*) AS cnt FROM source_registry WHERE enabled = 1").fetchone()["cnt"]
            errored = conn.execute("SELECT COUNT(*) AS cnt FROM source_registry WHERE error_count > 0").fetchone()["cnt"]
            row = conn.execute("SELECT MAX(last_run_at) AS last_run_at FROM source_registry").fetchone()
        return {
            "total": total,
            "enabled": enabled,
            "errored": errored,
            "last_run_at": row["last_run_at"],
        }

    def list_source_resources(self, source_id: str, limit: int = 50, offset: int = 0) -> list[SourceResourceRow]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    r.resource_id,
                    r.canonical_url,
                    r.source,
                    r.title,
                    r.published_at,
                    r.text,
                    r.original_url,
                    r.topics_json,
                    r.summary,
                    MAX(sii.last_seen_at) AS last_seen_at
                FROM source_item_index AS sii
                JOIN resources AS r
                    ON r.resource_id = sii.resource_id
                WHERE sii.source_id = ?
                GROUP BY r.resource_id
                ORDER BY MAX(sii.last_seen_at) DESC
                LIMIT ? OFFSET ?
                """,
                (source_id, limit, offset),
            ).fetchall()

        return [_row_to_source_resource(row) for row in rows]


def _row_to_source(row) -> SourceRecord:
    return SourceRecord(
        source_id=row["source_id"],
        source_type=row["source_type"],
        name=row["name"],
        endpoint=row["endpoint"],
        config=json.loads(row["config_json"] or "{}"),
        enabled=bool(row["enabled"]),
        schedule_minutes=row["schedule_minutes"] or 30,
        last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
        error_count=row["error_count"] or 0,
        last_error=row["last_error"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
    )


def _row_to_run(row) -> SourceRunLog:
    return SourceRunLog(
        run_id=row["run_id"],
        source_id=row["source_id"],
        started_at=datetime.fromisoformat(row["started_at"]),
        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        status=row["status"],
        fetched_count=row["fetched_count"] or 0,
        processed_count=row["processed_count"] or 0,
        error_message=row["error_message"],
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def _row_to_source_resource(row) -> SourceResourceRow:
    return SourceResourceRow(
        resource_id=row["resource_id"],
        canonical_url=row["canonical_url"],
        source=row["source"],
        title=row["title"],
        published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
        text=row["text"],
        original_url=row["original_url"],
        topics=json.loads(row["topics_json"] or "[]"),
        summary=row["summary"] or "",
        last_seen_at=datetime.fromisoformat(row["last_seen_at"]) if row["last_seen_at"] else None,
    )
