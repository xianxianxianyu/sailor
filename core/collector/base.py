from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
import logging
import time

from core.models import RawEntry

logger = logging.getLogger(__name__)


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
        total_collectors = len(self.collectors)
        for idx, collector in enumerate(self.collectors, start=1):
            collector_name = collector.__class__.__name__
            logger.info("[ingestion] collector start %s/%s name=%s", idx, total_collectors, collector_name)
            started = time.perf_counter()
            collected = collector.collect()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "[ingestion] collector done %s/%s name=%s entries=%s elapsed_ms=%s",
                idx,
                total_collectors,
                collector_name,
                len(collected),
                elapsed_ms,
            )

            for entry in collected:
                dedupe_key = f"{entry.source}:{entry.url}"
                merged[dedupe_key] = entry

            logger.info("[ingestion] merged entries=%s after=%s", len(merged), collector_name)
        return list(merged.values())
