from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from core.models import Job
from core.storage.job_repository import JobRepository
from .handlers import JobCancelled, JobHandler, RunContext

logger = logging.getLogger(__name__)


class JobRunner:
    """Unified job executor — manages job lifecycle and dispatches to handlers."""

    def __init__(self, job_repo: JobRepository, policy_gate=None, data_dir: Path | None = None) -> None:
        self.job_repo = job_repo
        self.policy_gate = policy_gate
        self.data_dir = data_dir
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def run(self, job_id: str) -> Job:
        job = self.job_repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        if job.status == "cancelled":
            return job

        handler = self._handlers.get(job.job_type)
        if not handler:
            raise ValueError(f"No handler registered for job type: {job.job_type}")

        ctx = RunContext(
            job_repo=self.job_repo,
            run_id=job.job_id,
            policy_check=self.policy_gate.check if self.policy_gate else None,
            policy_gate=self.policy_gate,
            data_dir=self.data_dir,
        )

        # queued -> running
        self.job_repo.update_status(job.job_id, "running")
        ctx.emit_event("JobStarted", {"job_type": job.job_type})

        MAX_RETRIES = 3
        output_json = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                output_json = handler.execute(job, ctx)
                # success
                break
            except JobCancelled as exc:
                if job.metadata:
                    self.job_repo.merge_metadata(job.job_id, job.metadata)
                self.job_repo.update_status(
                    job.job_id, "cancelled",
                    error_message=str(exc)[:500],
                )
                ctx.emit_event("JobCancelled", {"reason": str(exc)[:500]})
                logger.info("[runner] Job %s cancelled: %s", job_id, exc)
                return self.job_repo.get_job(job_id)  # type: ignore[return-value]
            except Exception as exc:
                if _is_transient(exc) and attempt < MAX_RETRIES:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "[runner] Job %s transient error (attempt %d/%d), retry in %ds: %s",
                        job_id, attempt + 1, MAX_RETRIES, wait, exc,
                    )
                    job.metadata["retry_count"] = attempt + 1
                    time.sleep(wait)
                    continue
                # permanent or exhausted retries
                error_class = "transient" if _is_transient(exc) else "permanent"
                self.job_repo.update_status(
                    job.job_id, "failed",
                    error_class=error_class,
                    error_message=str(exc)[:500],
                )
                ctx.emit_event("JobFailed", {"error_class": error_class, "error": str(exc)[:500]})
                logger.warning("[runner] Job %s failed: %s", job_id, exc)
                return self.job_repo.get_job(job_id)  # type: ignore[return-value]

        # Determine final status: handler can set error_class="partial" via metadata
        error_class = job.metadata.get("_error_class")
        status = "succeeded"
        if job.metadata:
            self.job_repo.merge_metadata(job.job_id, job.metadata)
        self.job_repo.update_status(
            job.job_id, status,
            error_class=error_class,
            output_json=output_json,
        )
        ctx.emit_event("JobFinished", {"status": status, "error_class": error_class})

        return self.job_repo.get_job(job_id)  # type: ignore[return-value]


def _is_transient(exc: Exception) -> bool:
    """Heuristic: network / timeout errors are transient."""
    name = type(exc).__name__.lower()
    return any(k in name for k in ("timeout", "connection", "network", "temporary"))
