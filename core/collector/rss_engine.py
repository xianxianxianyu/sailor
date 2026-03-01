from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path

from core.collector.base import Collector
from core.models import RawEntry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RSSCollector(Collector):
    seed_file: Path
    source_name: str = "rss"

    def collect(self) -> list[RawEntry]:
        if not self.seed_file.exists():
            logger.info("[collector:rss_seed] skipped seed file not found path=%s", self.seed_file)
            return []

        data = json.loads(self.seed_file.read_text(encoding="utf-8"))
        logger.info("[collector:rss_seed] loading seed entries=%s path=%s", len(data), self.seed_file)
        entries: list[RawEntry] = []

        for item in data:
            published_raw = item.get("published_at")
            published_at = datetime.fromisoformat(published_raw) if published_raw else None
            entries.append(
                RawEntry(
                    entry_id=str(item["entry_id"]),
                    feed_id=str(item.get("feed_id", "rss-feed")),
                    source=self.source_name,
                    title=item["title"],
                    url=item["url"],
                    content=item.get("content", ""),
                    published_at=published_at,
                )
            )
        logger.info("[collector:rss_seed] done emitted=%s", len(entries))
        return entries
