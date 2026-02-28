from __future__ import annotations

import json
import uuid
from datetime import datetime

from core.models import SniffResult, SnifferPack
from core.storage.db import Database


class SnifferRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # --- SniffResult ---

    def save_results(self, results: list[SniffResult]) -> int:
        if not results:
            return 0
        with self.db.connect() as conn:
            for r in results:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sniff_results
                        (result_id, channel, title, url, snippet, author,
                         published_at, media_type, metrics_json, raw_data_json,
                         query_keyword)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.result_id,
                        r.channel,
                        r.title,
                        r.url,
                        r.snippet,
                        r.author,
                        r.published_at.isoformat() if r.published_at else None,
                        r.media_type,
                        json.dumps(r.metrics),
                        json.dumps(r.raw_data),
                        r.query_keyword,
                    ),
                )
        return len(results)

    def list_results(self, keyword: str, limit: int = 50) -> list[SniffResult]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sniff_results WHERE query_keyword = ? ORDER BY created_at DESC LIMIT ?",
                (keyword, limit),
            ).fetchall()
        return [_row_to_result(row) for row in rows]

    # --- SnifferPack ---

    def create_pack(self, pack: SnifferPack) -> SnifferPack:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO sniffer_packs (pack_id, name, query_json, description, schedule_cron) VALUES (?, ?, ?, ?, ?)",
                (pack.pack_id, pack.name, pack.query_json, pack.description, pack.schedule_cron),
            )
            row = conn.execute("SELECT * FROM sniffer_packs WHERE pack_id = ?", (pack.pack_id,)).fetchone()
        return _row_to_pack(row)

    def list_packs(self) -> list[SnifferPack]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM sniffer_packs ORDER BY created_at DESC").fetchall()
        return [_row_to_pack(row) for row in rows]

    def get_pack(self, pack_id: str) -> SnifferPack | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM sniffer_packs WHERE pack_id = ?", (pack_id,)).fetchone()
        return _row_to_pack(row) if row else None

    def delete_pack(self, pack_id: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute("DELETE FROM sniffer_packs WHERE pack_id = ?", (pack_id,))
        return cursor.rowcount > 0

    def update_pack_schedule(self, pack_id: str, schedule_cron: str | None, next_run_at: str | None = None) -> SnifferPack | None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE sniffer_packs SET schedule_cron = ?, next_run_at = ? WHERE pack_id = ?",
                (schedule_cron, next_run_at, pack_id),
            )
            row = conn.execute("SELECT * FROM sniffer_packs WHERE pack_id = ?", (pack_id,)).fetchone()
        return _row_to_pack(row) if row else None

    def update_pack_last_run(self, pack_id: str, last_run_at: str, next_run_at: str | None = None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE sniffer_packs SET last_run_at = ?, next_run_at = ? WHERE pack_id = ?",
                (last_run_at, next_run_at, pack_id),
            )

    def list_scheduled_packs(self) -> list[SnifferPack]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sniffer_packs WHERE schedule_cron IS NOT NULL ORDER BY next_run_at ASC"
            ).fetchall()
        return [_row_to_pack(row) for row in rows]

    def get_result(self, result_id: str) -> SniffResult | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM sniff_results WHERE result_id = ?", (result_id,)).fetchone()
        return _row_to_result(row) if row else None

    def get_results_by_ids(self, result_ids: list[str]) -> list[SniffResult]:
        if not result_ids:
            return []
        placeholders = ",".join("?" for _ in result_ids)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM sniff_results WHERE result_id IN ({placeholders})",
                result_ids,
            ).fetchall()
        return [_row_to_result(row) for row in rows]

    # --- Summary Cache ---

    def get_cached_summary(self, cache_key: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT summary_json FROM summary_cache WHERE cache_key = ?", (cache_key,)).fetchone()
        return row["summary_json"] if row else None

    def set_cached_summary(self, cache_key: str, summary_json: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO summary_cache (cache_key, summary_json) VALUES (?, ?)",
                (cache_key, summary_json),
            )


def _row_to_result(row) -> SniffResult:
    return SniffResult(
        result_id=row["result_id"],
        channel=row["channel"],
        title=row["title"],
        url=row["url"],
        snippet=row["snippet"] or "",
        author=row["author"],
        published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
        media_type=row["media_type"] or "article",
        metrics=json.loads(row["metrics_json"] or "{}"),
        raw_data=json.loads(row["raw_data_json"] or "{}"),
        query_keyword=row["query_keyword"] or "",
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )


def _row_to_pack(row) -> SnifferPack:
    return SnifferPack(
        pack_id=row["pack_id"],
        name=row["name"],
        query_json=row["query_json"] or "{}",
        description=row["description"],
        schedule_cron=row["schedule_cron"],
        last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
        next_run_at=datetime.fromisoformat(row["next_run_at"]) if row["next_run_at"] else None,
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )
