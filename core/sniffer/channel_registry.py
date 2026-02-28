from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol, runtime_checkable

from core.models import SniffQuery, SniffResult

logger = logging.getLogger("sailor")


@runtime_checkable
class ChannelAdapter(Protocol):
    channel_id: str
    display_name: str
    icon: str
    tier: str  # "free" | "auth_required" | "premium"
    media_types: list[str]

    def check(self) -> dict:
        """Return {"status": "ok"|"warn"|"off", "message": str}."""
        ...

    def search(self, query: SniffQuery) -> list[SniffResult]:
        """Execute search and return standardized results."""
        ...


class ChannelRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.channel_id] = adapter

    def get(self, channel_id: str) -> ChannelAdapter | None:
        return self._adapters.get(channel_id)

    def list_channels(self) -> list[dict]:
        result = []
        for a in self._adapters.values():
            status = {"status": "ok", "message": ""}
            try:
                status = a.check()
            except Exception as exc:
                status = {"status": "off", "message": str(exc)}
            result.append({
                "channel_id": a.channel_id,
                "display_name": a.display_name,
                "icon": a.icon,
                "tier": a.tier,
                "media_types": a.media_types,
                "status": status["status"],
                "message": status["message"],
            })
        return result

    def search(self, query: SniffQuery) -> list[SniffResult]:
        """Search across selected channels in parallel."""
        channels = query.channels or list(self._adapters.keys())
        adapters = [self._adapters[c] for c in channels if c in self._adapters]

        if not adapters:
            return []

        all_results: list[SniffResult] = []
        with ThreadPoolExecutor(max_workers=min(len(adapters), 5)) as pool:
            futures = {pool.submit(a.search, query): a.channel_id for a in adapters}
            for future in as_completed(futures):
                cid = futures[future]
                try:
                    results = future.result(timeout=30)
                    all_results.extend(results)
                    logger.info(f"[sniffer] {cid} returned {len(results)} results")
                except Exception as exc:
                    logger.warning(f"[sniffer] {cid} search failed: {exc}")

        # Deduplicate by URL
        seen_urls: set[str] = set()
        deduped: list[SniffResult] = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                deduped.append(r)

        return deduped
