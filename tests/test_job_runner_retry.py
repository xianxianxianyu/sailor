"""Unit tests for JobRunner retry mechanism (P7.2)."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from core.models import Job
from core.runner.handlers import RunContext


def test_retry_transient_succeeds_on_second_attempt(db, job_repo):
    """Handler fails with ConnectionError on first attempt, succeeds on second."""
    from core.runner.job_runner import JobRunner

    runner = JobRunner(job_repo=job_repo)

    call_count = 0

    class TransientHandler:
        def execute(self, job: Job, ctx: RunContext) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("transient network error")
            return json.dumps({"result": "success"})

    runner.register("transient_test", TransientHandler())

    job = job_repo.create_job(Job(
        job_id="retry-test-001",
        job_type="transient_test",
        input_json="{}",
    ))

    with patch("core.runner.job_runner.time.sleep"):
        result = runner.run(job.job_id)

    assert result.status == "succeeded"
    assert result.metadata.get("retry_count") == 1
    assert call_count == 2


def test_retry_exhausted_marks_failed(db, job_repo):
    """Handler fails with ConnectionError 4 times, exhausts retries."""
    from core.runner.job_runner import JobRunner

    runner = JobRunner(job_repo=job_repo)

    class AlwaysFailHandler:
        def execute(self, job: Job, ctx: RunContext) -> str:
            raise ConnectionError("persistent network error")

    runner.register("always_fail", AlwaysFailHandler())

    job = job_repo.create_job(Job(
        job_id="retry-test-002",
        job_type="always_fail",
        input_json="{}",
    ))

    with patch("core.runner.job_runner.time.sleep"):
        result = runner.run(job.job_id)

    assert result.status == "failed"
    assert result.error_class == "transient"
    assert "network error" in (result.error_message or "")


def test_permanent_error_no_retry(db, job_repo):
    """Handler raises ValueError (permanent error), no retry attempted."""
    from core.runner.job_runner import JobRunner

    runner = JobRunner(job_repo=job_repo)

    call_count = 0

    class PermanentErrorHandler:
        def execute(self, job: Job, ctx: RunContext) -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("invalid input")

    runner.register("permanent_error", PermanentErrorHandler())

    job = job_repo.create_job(Job(
        job_id="retry-test-003",
        job_type="permanent_error",
        input_json="{}",
    ))

    result = runner.run(job.job_id)

    assert result.status == "failed"
    assert result.error_class == "permanent"
    assert call_count == 1  # only called once, no retry


def test_retry_count_recorded_in_metadata(db, job_repo):
    """Handler fails twice, succeeds on third attempt, retry_count=2."""
    from core.runner.job_runner import JobRunner

    runner = JobRunner(job_repo=job_repo)

    call_count = 0

    class TwoRetriesHandler:
        def execute(self, job: Job, ctx: RunContext) -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("transient error")
            return json.dumps({"result": "success"})

    runner.register("two_retries", TwoRetriesHandler())

    job = job_repo.create_job(Job(
        job_id="retry-test-004",
        job_type="two_retries",
        input_json="{}",
    ))

    with patch("core.runner.job_runner.time.sleep"):
        result = runner.run(job.job_id)

    assert result.status == "succeeded"
    assert result.metadata.get("retry_count") == 2
    assert call_count == 3


def test_retry_sleep_called(db, job_repo):
    """Verify exponential backoff: sleep(1), sleep(2), sleep(4)."""
    from core.runner.job_runner import JobRunner

    runner = JobRunner(job_repo=job_repo)

    call_count = 0

    class ThreeRetriesHandler:
        def execute(self, job: Job, ctx: RunContext) -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ConnectionError("transient error")
            return json.dumps({"result": "success"})

    runner.register("three_retries", ThreeRetriesHandler())

    job = job_repo.create_job(Job(
        job_id="retry-test-005",
        job_type="three_retries",
        input_json="{}",
    ))

    with patch("core.runner.job_runner.time.sleep") as mock_sleep:
        result = runner.run(job.job_id)

    assert result.status == "succeeded"
    assert mock_sleep.call_count == 3
    # Verify exponential backoff: 2^0=1, 2^1=2, 2^2=4
    assert mock_sleep.call_args_list[0][0][0] == 1
    assert mock_sleep.call_args_list[1][0][0] == 2
    assert mock_sleep.call_args_list[2][0][0] == 4
