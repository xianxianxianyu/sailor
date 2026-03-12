from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

from backend.worker import JobWorker
from core.models import Job
from core.runner.handlers import RunContext
from core.runner.job_runner import JobRunner
from core.storage.db import Database
from core.storage.job_repository import JobRepository
class CooperativeCancelHandler:
    def __init__(self, started: threading.Event) -> None:
        self.started = started

    def execute(self, job: Job, ctx: RunContext) -> str:
        self.started.set()
        for _ in range(50):
            time.sleep(0.01)
            ctx.raise_if_cancel_requested("Cancelled by test")
        return "{}"


def test_running_job_can_finish_as_cancelled(tmp_path: Path):
    db = Database(tmp_path / "cancel.db")
    db.init_schema()
    job_repo = JobRepository(db)
    runner = JobRunner(job_repo)

    started = threading.Event()
    runner.register("cooperative_cancel", CooperativeCancelHandler(started))

    job = job_repo.create_job(Job(
        job_id="job_cancel_1",
        job_type="cooperative_cancel",
        input_json="{}",
    ))

    def request_cancel() -> None:
        assert started.wait(timeout=2)
        job_repo.request_cancel(job.job_id)

    canceller = threading.Thread(target=request_cancel)
    canceller.start()
    result = runner.run(job.job_id)
    canceller.join(timeout=2)

    assert result.status == "cancelled"
    assert result.error_message == "Cancelled by test"
    assert result.metadata.get("cancel_requested") is True


def test_worker_signal_requests_cancel_for_current_job(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("signal.signal", lambda *_args, **_kwargs: None)

    db = Database(tmp_path / "worker_cancel.db")
    db.init_schema()
    job_repo = JobRepository(db)

    job = job_repo.create_job(Job(
        job_id="job_worker_cancel",
        job_type="test",
        input_json="{}",
    ))
    job_repo.update_status(job.job_id, "running")

    worker = JobWorker(
        container=SimpleNamespace(job_repo=job_repo, job_runner=SimpleNamespace()),
        poll_interval=1,
        stale_minutes=30,
        job_types=None,
    )
    worker._current_job_id = job.job_id

    worker._stop(2, None)

    stored = job_repo.get_job(job.job_id)
    assert worker._stopped is True
    assert stored is not None
    assert stored.status == "running"
    assert stored.metadata.get("cancel_requested") is True
