from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.collector.base import Collector
from core.models import RawEntry


@dataclass(slots=True)
class RSSCollector(Collector):
    seed_file: Path
    source_name: str = "rss"

    def collect(self) -> list[RawEntry]:
        if not self.seed_file.exists():
            return []

        data = json.loads(self.seed_file.read_text(encoding="utf-8"))
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
        return entries
