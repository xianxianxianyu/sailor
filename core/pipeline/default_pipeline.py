from __future__ import annotations

from core.pipeline.base import PreprocessPipeline
from core.pipeline.stages import (
    BuildResourceStage,
    CleanStage,
    EnrichStage,
    FetchExtractStage,
    NormalizeStage,
)


def build_default_pipeline() -> PreprocessPipeline:
    return PreprocessPipeline(
        stages=[
            NormalizeStage(),
            FetchExtractStage(),
            CleanStage(),
            EnrichStage(),
            BuildResourceStage(),
        ]
    )
