from __future__ import annotations

import logging
import uuid
from datetime import datetime

from core.models import SniffQuery, SniffResult
from core.storage.db import Database

logger = logging.getLogger(__name__)


class RSSAdapter:
    """Search existing local RSS/feed resources by keyword."""

    channel_id = "rss"
    display_name = "RSS 订阅"
    icon = "📡"
    tier = "free"
    media_types = ["article"]

    def __init__(self, db: Database) -> None:
        self.db = db

    def check(self) -> dict:
        try:
            with self.db.connect() as conn:
                row = conn.execute("SELECT COUNT(*) as cnt FROM resources").fetchone()
                count = row["cnt"] if row else 0
            if count > 0:
                return {"status": "ok", "message": f"{count} resources in local DB"}
            return {"status": "warn", "message": "No resources in local DB yet"}
        except Exception as exc:
            return {"status": "off", "message": str(exc)}

    def search(self, query: SniffQuery) -> list[SniffResult]:
        limit = min(query.max_results_per_channel, 50)
        keyword = f"%{query.keyword}%"

        time_clause = ""
        if query.time_range == "24h":
            time_clause = "AND published_at >= datetime('now', '-1 day')"
        elif query.time_range == "7d":
            time_clause = "AND published_at >= datetime('now', '-7 days')"
        elif query.time_range == "30d":
            time_clause = "AND published_at >= datetime('now', '-30 days')"

        order = "published_at DESC"
        if query.sort_by == "relevance":
            order = "published_at DESC"  # SQLite has no relevance ranking; fall back to recency

        sql = f"""
            SELECT resource_id, title, original_url, summary, source, published_at
            FROM resources
            WHERE (title LIKE ? OR summary LIKE ?)
            {time_clause}
            ORDER BY {order}
            LIMIT ?
        """

        try:
            with self.db.connect() as conn:
                rows = conn.execute(sql, (keyword, keyword, limit)).fetchall()
        except Exception as exc:
            logger.warning(f"[sniffer:rss] query failed: {exc}")
            return []

        results: list[SniffResult] = []
        for row in rows:
            pub = None
            if row["published_at"]:
                try:
                    pub = datetime.fromisoformat(row["published_at"])
                except Exception:
                    pass

            results.append(SniffResult(
                result_id=f"rss_{row['resource_id']}",
                channel="rss",
                title=row["title"],
                url=row["original_url"],
                snippet=row["summary"][:200] if row["summary"] else "",
                author=row["source"],
                published_at=pub,
                media_type="article",
                metrics={},
                raw_data={},
                query_keyword=query.keyword,
            ))
        return results
