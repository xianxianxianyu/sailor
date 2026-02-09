from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.models import RawEntry, Resource


@dataclass(slots=True)
class PipelineContext:
    entry: RawEntry
    canonical_url: str = ""
    raw_html: str = ""
    extracted_text: str = ""
    clean_text: str = ""
    topics: list[str] | None = None
    summary: str = ""
    resource: Resource | None = None


class PipelineStage(ABC):
    @abstractmethod
    def run(self, context: PipelineContext) -> PipelineContext:
        """Mutate context and return it for next stage."""


class PreprocessPipeline:
    """Base pipeline class that orchestrates all stage subclasses."""

    def __init__(self, stages: list[PipelineStage]) -> None:
        self.stages = stages

    def process(self, entry: RawEntry) -> Resource:
        context = PipelineContext(entry=entry)
        for stage in self.stages:
            context = stage.run(context)

        if context.resource is None:
            msg = "Pipeline completed without creating a resource"
            raise ValueError(msg)
        return context.resource
