from __future__ import annotations

from dataclasses import dataclass

from core.collector.base import CollectionEngine
from core.pipeline.base import PreprocessPipeline
from core.storage.repositories import ResourceRepository


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
        entries = self.engine.collect()
        processed = 0
        for entry in entries:
            resource = self.pipeline.process(entry)
            self.resource_repo.upsert(resource)
            processed += 1

        return IngestionResult(collected_count=len(entries), processed_count=processed)
