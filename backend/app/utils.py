from __future__ import annotations

import time

from fastapi import HTTPException

from core.models import Job
from core.storage.job_repository import JobRepository


def wait_for_job(
    job_repo: JobRepository,
    job_id: str,
    timeout: int = 120,
    poll_interval: float = 1.0,
) -> Job:
    """Poll until job completes; returns last known job state on timeout."""
    deadline = time.monotonic() + timeout
    last_job: Job | None = None
    while time.monotonic() < deadline:
        job = job_repo.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        last_job = job
        if job and job.status in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(poll_interval)
    if last_job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return last_job
