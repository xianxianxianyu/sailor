from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
import logging
from urllib import error, parse, request

from core.collector.base import Collector
from core.models import RawEntry

logger = logging.getLogger("sailor")


@dataclass(slots=True)
class MinifluxCollector(Collector):
    base_url: str
    token: str
    source_name: str = "rsshub"
    limit: int = 100

    def collect(self) -> list[RawEntry]:
        if not self.base_url or not self.token:
            logger.info("[collector:miniflux] skipped not configured")
            return []

        query = parse.urlencode({"status": "unread", "limit": self.limit})
        endpoint = f"{self.base_url.rstrip('/')}/v1/entries?{query}"
        req = request.Request(endpoint, headers={"X-Auth-Token": self.token})

        try:
            with request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.error("[collector:miniflux] fetch failed err=%s", exc)
            return []

        entries: list[RawEntry] = []
        for item in payload.get("entries", []):
            published_at = _parse_dt(item.get("published_at"))
            entries.append(
                RawEntry(
                    entry_id=str(item["id"]),
                    feed_id=str(item.get("feed_id", "miniflux-feed")),
                    source=self.source_name,
                    title=item.get("title", "(untitled)"),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    published_at=published_at,
                )
            )

        logger.info("[collector:miniflux] done fetched=%s", len(entries))
        return entries


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None

    # Miniflux can return RFC3339 timestamps with trailing Z.
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
