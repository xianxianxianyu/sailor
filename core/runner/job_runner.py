from __future__ import annotations

import logging
import uuid
from datetime import datetime

from core.models import Job
from core.storage.job_repository import JobRepository
from .handlers import JobHandler, RunContext

logger = logging.getLogger(__name__)


class JobRunner:
    """Unified job executor — manages job lifecycle and dispatches to handlers."""

    def __init__(self, job_repo: JobRepository, policy_gate=None) -> None:
        self.job_repo = job_repo
        self.policy_gate = policy_gate
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def run(self, job_id: str) -> Job:
        job = self.job_repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        handler = self._handlers.get(job.job_type)
        if not handler:
            raise ValueError(f"No handler registered for job type: {job.job_type}")

        ctx = RunContext(
            job_repo=self.job_repo,
            run_id=job.job_id,
            policy_check=self.policy_gate.check if self.policy_gate else None,
            policy_gate=self.policy_gate,
        )

        # queued -> running
        self.job_repo.update_status(job.job_id, "running")
        ctx.emit_event("JobStarted", {"job_type": job.job_type})

        try:
            output_json = handler.execute(job, ctx)
            # Determine final status: handler can set error_class="partial" via metadata
            error_class = job.metadata.get("_error_class")
            status = "succeeded"
            self.job_repo.update_status(
                job.job_id, status,
                error_class=error_class,
                output_json=output_json,
            )
            ctx.emit_event("JobFinished", {"status": status, "error_class": error_class})
        except Exception as exc:
            error_class = "transient" if _is_transient(exc) else "permanent"
            self.job_repo.update_status(
                job.job_id, "failed",
                error_class=error_class,
                error_message=str(exc)[:500],
            )
            ctx.emit_event("JobFailed", {"error_class": error_class, "error": str(exc)[:500]})
            logger.warning("[runner] Job %s failed: %s", job_id, exc)

        return self.job_repo.get_job(job_id)  # type: ignore[return-value]


def _is_transient(exc: Exception) -> bool:
    """Heuristic: network / timeout errors are transient."""
    name = type(exc).__name__.lower()
    return any(k in name for k in ("timeout", "connection", "network", "temporary"))
