"""IngestionHandler — JobHandler that runs the IngestionService via the job system."""
from __future__ import annotations

import json
import logging

from core.models import Job
from core.services.ingestion import IngestionService
from .handlers import RunContext

logger = logging.getLogger(__name__)


class IngestionHandler:
    """Wraps IngestionService.run() as a job handler for runner orchestration."""

    def __init__(self, ingestion_service: IngestionService) -> None:
        self.ingestion_service = ingestion_service

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        ctx.emit_event("IngestionStarted")

        result = self.ingestion_service.run()

        ctx.emit_event("IngestionFinished", {
            "collected_count": result.collected_count,
            "processed_count": result.processed_count,
        })

        return json.dumps({
            "collected_count": result.collected_count,
            "processed_count": result.processed_count,
        })
