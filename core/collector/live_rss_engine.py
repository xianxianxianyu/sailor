from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import feedparser

from core.collector.base import Collector
from core.models import RawEntry
from core.storage.feed_repository import FeedRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LiveRSSCollector(Collector):
    feed_repo: FeedRepository
    source_name: str = "live_rss"

    def collect(self) -> list[RawEntry]:
        feeds = self.feed_repo.list_feeds(enabled_only=True)
        logger.info("[collector:live_rss] start enabled_feeds=%s", len(feeds))
        entries: list[RawEntry] = []

        for idx, feed in enumerate(feeds, start=1):
            if idx == 1 or idx % 20 == 0 or idx == len(feeds):
                logger.info("[collector:live_rss] progress feed=%s/%s", idx, len(feeds))
            try:
                parsed = feedparser.parse(feed.xml_url)
                if parsed.bozo and not parsed.entries:
                    raise ValueError(f"Feed 解析失败: {parsed.bozo_exception}")

                for item in parsed.entries:
                    entry = _to_raw_entry(item, feed.feed_id, self.source_name)
                    if entry:
                        entries.append(entry)

                self.feed_repo.update_feed_status(
                    feed_id=feed.feed_id,
                    last_fetched_at=datetime.utcnow(),
                    error_count=0,
                    last_error="",
                )
            except Exception as exc:
                logger.warning("抓取 Feed %s 失败: %s", feed.xml_url, exc)
                self.feed_repo.update_feed_status(
                    feed_id=feed.feed_id,
                    error_count=feed.error_count + 1,
                    last_error=str(exc)[:500],
                )

        logger.info("[collector:live_rss] done emitted=%s", len(entries))
        return entries


def _to_raw_entry(item: dict, feed_id: str, source: str) -> RawEntry | None:
    link = item.get("link", "")
    if not link:
        return None

    entry_id = item.get("id", link)
    title = item.get("title", "(untitled)")

    # 优先取 content，其次 summary
    content = ""
    if item.get("content"):
        content = item["content"][0].get("value", "")
    elif item.get("summary"):
        content = item["summary"]

    published_at = _parse_published(item)

    return RawEntry(
        entry_id=str(entry_id),
        feed_id=str(feed_id),
        source=source,
        title=title,
        url=link,
        content=content,
        published_at=published_at,
    )


def _parse_published(item: dict) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        time_struct = item.get(field)
        if time_struct:
            try:
                return datetime(*time_struct[:6])
            except (TypeError, ValueError):
                continue
    return None
