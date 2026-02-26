from __future__ import annotations

from dataclasses import dataclass
import logging
import time

from core.collector.base import CollectionEngine
from core.pipeline.base import PreprocessPipeline
from core.storage.repositories import ResourceRepository

logger = logging.getLogger("sailor")


@dataclass(slots=True)
class IngestionResult:
    collected_count: int
    processed_count: int


class IngestionService:
    def __init__(
        self,
        engine: CollectionEngine,
        pipeline: PreprocessPipeline,
        resource_repo: ResourceRepository,
    ) -> None:
        self.engine = engine
        self.pipeline = pipeline
        self.resource_repo = resource_repo

    def run(self) -> IngestionResult:
        started = time.perf_counter()
        logger.info("[ingestion] run start")

        entries = self.engine.collect()
        logger.info("[ingestion] collect completed total_entries=%s", len(entries))

        processed = 0
        for idx, entry in enumerate(entries, start=1):
            try:
                resource = self.pipeline.process(entry)
                self.resource_repo.upsert(resource)
                processed += 1
            except Exception:
                logger.exception(
                    "[ingestion] process failed index=%s source=%s entry_id=%s url=%s",
                    idx,
                    entry.source,
                    entry.entry_id,
                    entry.url,
                )
                raise

            if idx % 25 == 0 or idx == len(entries):
                logger.info("[ingestion] process progress processed=%s/%s", processed, len(entries))

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "[ingestion] run done collected=%s processed=%s elapsed_ms=%s",
            len(entries),
            processed,
            elapsed_ms,
        )

        return IngestionResult(collected_count=len(entries), processed_count=processed)
