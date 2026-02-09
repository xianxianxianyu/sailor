from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict

from core.models import RawEntry


class Collector(ABC):
    @abstractmethod
    def collect(self) -> list[RawEntry]:
        """Fetch new entries from one upstream source."""


class CollectionEngine:
    """Unified ingestion engine for RSS and RSSHub+Miniflux sources."""

    def __init__(self, collectors: list[Collector]) -> None:
        self.collectors = collectors

    def collect(self) -> list[RawEntry]:
        merged: "OrderedDict[str, RawEntry]" = OrderedDict()
        for collector in self.collectors:
            for entry in collector.collect():
                dedupe_key = f"{entry.source}:{entry.url}"
                merged[dedupe_key] = entry
        return list(merged.values())
