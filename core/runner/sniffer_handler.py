"""SnifferHandler — JobHandler implementation for sniffer search runs."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from core.models import Job, JobBudget, SniffQuery, SnifferRunLog
from core.sniffer.summary_engine import SummaryEngine
from core.sniffer.tool_module import SnifferToolModule
from core.storage.job_repository import JobRepository
from .handlers import RunContext

logger = logging.getLogger(__name__)


class SnifferHandler:
    """Executes a sniffer search inside the JobRunner lifecycle."""

    def __init__(
        self,
        tool_module: SnifferToolModule,
        summary_engine: SummaryEngine,
        job_repo: JobRepository,
    ) -> None:
        self.tool_module = tool_module
        self.summary_engine = summary_engine
        self.job_repo = job_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json)

        query = SniffQuery(
            keyword=input_data["keyword"],
            channels=input_data.get("channels", []),
            time_range=input_data.get("time_range", "all"),
            sort_by=input_data.get("sort_by", "relevance"),
            max_results_per_channel=input_data.get("max_results_per_channel", 10),
        )
        pack_id: str | None = input_data.get("pack_id")

        # Parse optional budget
        budget = None
        if "budget" in input_data:
            b = input_data["budget"]
            budget = JobBudget(
                max_workers=b.get("max_workers", 5),
                deadline_ms=b.get("deadline_ms", 60000),
                max_tool_calls=b.get("max_tool_calls", 20),
            )

        # Dual-write: SnifferRunLog for backward compat
        run_id = uuid.uuid4().hex[:12]
        self.job_repo.save_sniffer_run(SnifferRunLog(
            run_id=run_id,
            job_id=job.job_id,
            query_json=json.dumps({
                "keyword": query.keyword,
                "channels": query.channels,
                "time_range": query.time_range,
                "sort_by": query.sort_by,
                "max_results_per_channel": query.max_results_per_channel,
            }),
            pack_id=pack_id,
            status="running",
            channels_used=query.channels,
            started_at=datetime.utcnow(),
        ))

        ctx.emit_event(
            "SnifferSearchStarted",
            payload={"keyword": query.keyword, "channels": query.channels},
            entity_refs={"sniffer_run_id": run_id},
            actor="user",
        )

        try:
            worker_results = self.tool_module.search_channels(query, ctx, budget)
            results = worker_results.results
            summary = self.summary_engine.summarize(results, query.keyword)

            # Determine partial success
            if worker_results.channels_failed and worker_results.channels_succeeded:
                job.metadata["_error_class"] = "partial"

            # Dual-write: finish SnifferRunLog
            status = "succeeded" if worker_results.channels_succeeded else "failed"
            self.job_repo.finish_sniffer_run(
                run_id, status, len(results),
                channels_succeeded=worker_results.channels_succeeded,
                channels_failed=worker_results.channels_failed,
            )

            ctx.emit_event(
                "SnifferSearchFinished",
                payload={
                    "result_count": len(results),
                    "channels_succeeded": worker_results.channels_succeeded,
                    "channels_failed": worker_results.channels_failed,
                },
                entity_refs={"sniffer_run_id": run_id},
            )

            result_ids = [r.result_id for r in results]
            return json.dumps({
                "sniffer_run_id": run_id,
                "result_count": len(results),
                "result_ids": result_ids,
                "summary": summary,
                "channels_succeeded": worker_results.channels_succeeded,
                "channels_failed": worker_results.channels_failed,
            })

        except Exception as exc:
            self.job_repo.finish_sniffer_run(run_id, "failed", 0, error=str(exc)[:500])
            raise
