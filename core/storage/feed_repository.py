from __future__ import annotations

import hashlib
from datetime import datetime

from core.models import RSSFeed
from core.storage.db import Database


class FeedRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def import_feeds(self, feeds: list[dict]) -> int:
        """批量导入 Feed，返回新增数量。"""
        imported = 0
        with self.db.connect() as conn:
            for feed in feeds:
                feed_id = _make_feed_id(feed["xml_url"])
                try:
                    conn.execute(
                        """
                        INSERT INTO rss_feeds (feed_id, name, xml_url, html_url)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(xml_url) DO UPDATE SET
                            name=excluded.name,
                            html_url=excluded.html_url
                        """,
                        (feed_id, feed["name"], feed["xml_url"], feed.get("html_url")),
                    )
                    imported += 1
                except Exception:
                    continue
        return imported

    def list_feeds(self, enabled_only: bool = False) -> list[RSSFeed]:
        query = "SELECT * FROM rss_feeds"
        params: list = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY name ASC"

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_feed(row) for row in rows]

    def update_feed_status(
        self,
        feed_id: str,
        last_fetched_at: datetime | None = None,
        error_count: int | None = None,
        last_error: str | None = None,
    ) -> None:
        updates: list[str] = []
        params: list = []

        if last_fetched_at is not None:
            updates.append("last_fetched_at = ?")
            params.append(last_fetched_at.isoformat())
        if error_count is not None:
            updates.append("error_count = ?")
            params.append(error_count)
        if last_error is not None:
            updates.append("last_error = ?")
            params.append(last_error)

        if not updates:
            return

        params.append(feed_id)
        sql = f"UPDATE rss_feeds SET {', '.join(updates)} WHERE feed_id = ?"
        with self.db.connect() as conn:
            conn.execute(sql, params)

    def add_feed(self, name: str, xml_url: str, html_url: str | None = None) -> RSSFeed:
        feed_id = _make_feed_id(xml_url)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO rss_feeds (feed_id, name, xml_url, html_url) VALUES (?, ?, ?, ?) ON CONFLICT(xml_url) DO NOTHING",
                (feed_id, name, xml_url, html_url),
            )
            row = conn.execute("SELECT * FROM rss_feeds WHERE feed_id = ?", (feed_id,)).fetchone()
        return _row_to_feed(row)

    def delete_feed(self, feed_id: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute("DELETE FROM rss_feeds WHERE feed_id = ?", (feed_id,))
        return cursor.rowcount > 0

    def toggle_enabled(self, feed_id: str, enabled: bool) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE rss_feeds SET enabled = ? WHERE feed_id = ?",
                (1 if enabled else 0, feed_id),
            )

    def list_feed_resources(self, feed_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        """获取 RSS 源的资源列表"""
        with self.db.connect() as conn:
            # 先获取 feed 的 name
            feed_row = conn.execute("SELECT name FROM rss_feeds WHERE feed_id = ?", (feed_id,)).fetchone()
            if not feed_row:
                return []
            feed_name = feed_row["name"]

            rows = conn.execute(
                """
                SELECT
                    resource_id,
                    canonical_url,
                    source,
                    title,
                    published_at,
                    text,
                    original_url,
                    topics_json,
                    summary,
                    created_at AS last_seen_at
                FROM resources
                WHERE source = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (feed_name, limit, offset),
            ).fetchall()

        return [dict(row) for row in rows]


def _make_feed_id(xml_url: str) -> str:
    return "feed_" + hashlib.sha256(xml_url.encode()).hexdigest()[:12]


def _row_to_feed(row) -> RSSFeed:
    return RSSFeed(
        feed_id=row["feed_id"],
        name=row["name"],
        xml_url=row["xml_url"],
        html_url=row["html_url"],
        enabled=bool(row["enabled"]),
        last_fetched_at=datetime.fromisoformat(row["last_fetched_at"]) if row["last_fetched_at"] else None,
        error_count=row["error_count"] or 0,
        last_error=row["last_error"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )
