"""IntelligenceHandler — JobHandler for ResourceIntelligenceEngine runs."""
from __future__ import annotations

import json
import logging

from core.engines.intelligence import ResourceIntelligenceEngine
from core.models import Job
from .handlers import RunContext

logger = logging.getLogger(__name__)


class IntelligenceHandler:
    """Executes a resource intelligence run (tagging + analysis) via the Engine."""

    def __init__(self, engine: ResourceIntelligenceEngine) -> None:
        self.engine = engine

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json) if job.input_json else {}
        resource_ids: list[str] | None = input_data.get("resource_ids")

        ctx.emit_event("IntelligenceRunStarted", {"resource_ids": resource_ids})

        results = self.engine.process(resource_ids, ctx=ctx)

        completed = sum(1 for r in results if r.analysis_status == "completed")
        failed = sum(1 for r in results if r.analysis_status == "failed")

        ctx.emit_event("IntelligenceRunFinished", {
            "total": len(results),
            "completed": completed,
            "failed": failed,
        })

        return json.dumps({
            "total": len(results),
            "completed": completed,
            "failed": failed,
            "results": [
                {"resource_id": r.resource_id, "tags": r.tags, "status": r.analysis_status}
                for r in results
            ],
        })
