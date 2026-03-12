"""Independent Worker process — polls and executes queued jobs.

Start:
    python -m backend.worker

Environment variables:
    WORKER_POLL_INTERVAL  Poll interval in seconds (default: 5)
    WORKER_STALE_MINUTES  Minutes before a running job is considered stale (default: 30)
    WORKER_JOB_TYPES      Optional comma-separated job_type filter
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.container import build_container  # noqa: E402

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(
        self,
        container,
        poll_interval: int,
        stale_minutes: int,
        job_types: list[str] | None,
    ):
        self.container = container
        self.job_repo = container.job_repo
        self.job_runner = container.job_runner
        self.poll_interval = poll_interval
        self.stale_minutes = stale_minutes
        self.job_types = job_types
        self._stopped = False
        self._current_job_id: str | None = None
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, signum, frame):
        logger.info("[worker] Signal %s received, stopping...", signum)
        self._stopped = True
        if self._current_job_id:
            updated = self.job_repo.request_cancel(self._current_job_id)
            if updated:
                logger.info(
                    "[worker] Requested cancellation for running job_id=%s",
                    self._current_job_id,
                )

    def start(self):
        logger.info(
            "[worker] started poll_interval=%ds stale_minutes=%d job_types=%s",
            self.poll_interval,
            self.stale_minutes,
            self.job_types or "all",
        )
        recovered = self.job_repo.reset_stale_running_jobs(self.stale_minutes)
        if recovered:
            logger.warning("[worker] Reset %d stale running jobs to queued", recovered)

        while not self._stopped:
            try:
                self._tick()
            except Exception:
                logger.exception("[worker] Tick error")
            time.sleep(self.poll_interval)

        logger.info("[worker] stopped")

    def _tick(self):
        job = self.job_repo.fetch_and_lock_next_queued_job(job_types=self.job_types)
        if not job:
            return
        logger.info("[worker] executing job_id=%s type=%s", job.job_id, job.job_type)
        # job_runner.run() advances the job from running → succeeded/failed
        self._current_job_id = job.job_id
        try:
            self.job_runner.run(job.job_id)
        finally:
            self._current_job_id = None


def main():
    poll_interval = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
    stale_minutes = int(os.getenv("WORKER_STALE_MINUTES", "30"))
    raw_types = os.getenv("WORKER_JOB_TYPES", "")
    job_types = [t.strip() for t in raw_types.split(",") if t.strip()] or None

    container = build_container(PROJECT_ROOT)
    JobWorker(container, poll_interval, stale_minutes, job_types).start()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    main()
