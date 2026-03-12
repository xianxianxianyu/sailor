"""Job Idempotency Tests

Tests for deterministic job_id generation and idempotent job creation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.storage.db import Database
from core.storage.job_repository import JobRepository, generate_deterministic_job_id


@pytest.fixture
def job_repo(tmp_path: Path) -> JobRepository:
    """Create temporary JobRepository"""
    db_path = tmp_path / "test_job_idempotency.db"
    db = Database(db_path)
    db.init_schema()
    return JobRepository(db)


def test_generate_deterministic_job_id_consistency():
    """Verify same inputs produce same job_id"""
    job_type = "board_snapshot"
    idempotency_key = "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"

    job_id1 = generate_deterministic_job_id(job_type, idempotency_key)
    job_id2 = generate_deterministic_job_id(job_type, idempotency_key)

    assert job_id1 == job_id2
    assert job_id1.startswith("job_")
    assert len(job_id1) == 16  # "job_" + 12 hex chars


def test_generate_deterministic_job_id_different_inputs():
    """Verify different inputs produce different job_ids"""
    job_id1 = generate_deterministic_job_id(
        "board_snapshot",
        "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"
    )
    job_id2 = generate_deterministic_job_id(
        "board_snapshot",
        "v1:board_snapshot:board_456:2024-01-01:2024-01-02:abc"
    )
    job_id3 = generate_deterministic_job_id(
        "research_run",
        "v1:research_run:prog_123:2024-01-01:2024-01-07"
    )

    assert job_id1 != job_id2
    assert job_id1 != job_id3
    assert job_id2 != job_id3


def test_create_job_idempotent_new_job(job_repo: JobRepository):
    """Create job with idempotency key"""
    job_type = "board_snapshot"
    idempotency_key = "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"
    input_json = {"board_id": "board_123", "window": {"since": "2024-01-01", "until": "2024-01-02"}}

    job_id, is_new = job_repo.create_job_idempotent(
        job_type=job_type,
        idempotency_key=idempotency_key,
        input_json=input_json,
    )

    assert is_new is True
    assert job_id.startswith("job_")

    # Verify job can be retrieved
    job = job_repo.get_job(job_id)
    assert job is not None
    assert job.job_id == job_id
    assert job.job_type == job_type
    assert job.status == "queued"
    assert json.loads(job.input_json) == input_json


def test_create_job_idempotent_existing_job(job_repo: JobRepository):
    """Create job twice with same idempotency key"""
    job_type = "board_snapshot"
    idempotency_key = "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"
    input_json = {"board_id": "board_123"}

    # First call - creates new job
    job_id1, is_new1 = job_repo.create_job_idempotent(
        job_type=job_type,
        idempotency_key=idempotency_key,
        input_json=input_json,
    )

    # Second call - returns existing job
    job_id2, is_new2 = job_repo.create_job_idempotent(
        job_type=job_type,
        idempotency_key=idempotency_key,
        input_json=input_json,
    )

    assert is_new1 is True
    assert is_new2 is False
    assert job_id1 == job_id2


def test_create_job_idempotent_different_keys(job_repo: JobRepository):
    """Create jobs with different idempotency keys"""
    job_type = "board_snapshot"

    job_id1, is_new1 = job_repo.create_job_idempotent(
        job_type=job_type,
        idempotency_key="v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc",
        input_json={"board_id": "board_123"},
    )

    job_id2, is_new2 = job_repo.create_job_idempotent(
        job_type=job_type,
        idempotency_key="v1:board_snapshot:board_456:2024-01-01:2024-01-02:abc",
        input_json={"board_id": "board_456"},
    )

    assert is_new1 is True
    assert is_new2 is True
    assert job_id1 != job_id2

    # Verify both jobs exist independently
    job1 = job_repo.get_job(job_id1)
    job2 = job_repo.get_job(job_id2)
    assert job1 is not None
    assert job2 is not None
    assert job1.job_id != job2.job_id


def test_find_job_by_idempotency_key(job_repo: JobRepository):
    """Find job using idempotency key"""
    job_type = "research_run"
    idempotency_key = "v1:research_run:prog_ai:2024-01-01:2024-01-07"
    input_json = {"program_id": "prog_ai", "window": {"since": "2024-01-01", "until": "2024-01-07"}}

    # Create job
    job_id, is_new = job_repo.create_job_idempotent(
        job_type=job_type,
        idempotency_key=idempotency_key,
        input_json=input_json,
    )

    # Find job using idempotency key
    found_job = job_repo.find_job_by_idempotency_key(job_type, idempotency_key)

    assert found_job is not None
    assert found_job.job_id == job_id
    assert found_job.job_type == job_type
    assert json.loads(found_job.input_json) == input_json


def test_idempotency_key_format_examples(job_repo: JobRepository):
    """Test with realistic idempotency keys for each job_type"""

    # board_snapshot
    config_hash = hashlib.sha256(
        json.dumps({"max_items": 100}, sort_keys=True).encode()
    ).hexdigest()[:8]
    job_id1, is_new1 = job_repo.create_job_idempotent(
        job_type="board_snapshot",
        idempotency_key=f"v1:board_snapshot:board_hn_top:2024-01-01:2024-01-02:{config_hash}",
        input_json={"board_id": "board_hn_top", "config": {"max_items": 100}},
    )
    assert is_new1 is True

    # board_run
    job_id2, is_new2 = job_repo.create_job_idempotent(
        job_type="board_run",
        idempotency_key="v1:board_run:board_hn_top:snap_001:snap_000",
        input_json={"board_id": "board_hn_top", "snapshot_id": "snap_001", "baseline_snapshot_id": "snap_000"},
    )
    assert is_new2 is True

    # research_run
    job_id3, is_new3 = job_repo.create_job_idempotent(
        job_type="research_run",
        idempotency_key="v1:research_run:prog_ai_papers:2024-01-01:2024-01-07",
        input_json={"program_id": "prog_ai_papers", "window": {"since": "2024-01-01", "until": "2024-01-07"}},
    )
    assert is_new3 is True

    # issue_compose
    bundles_hash = hashlib.sha256(
        json.dumps(["bundle_1", "bundle_2"], sort_keys=True).encode()
    ).hexdigest()[:8]
    job_id4, is_new4 = job_repo.create_job_idempotent(
        job_type="issue_compose",
        idempotency_key=f"v1:issue_compose:follow_weekly:2024-01-01:2024-01-07:{bundles_hash}",
        input_json={"follow_id": "follow_weekly", "bundles": ["bundle_1", "bundle_2"]},
    )
    assert is_new4 is True

    # Verify all jobs have different IDs
    assert len({job_id1, job_id2, job_id3, job_id4}) == 4


def test_create_job_idempotent_with_metadata(job_repo: JobRepository):
    """Test idempotent job creation with metadata"""
    job_type = "board_snapshot"
    idempotency_key = "v1:board_snapshot:board_123:2024-01-01:2024-01-02:abc"
    input_json = {"board_id": "board_123"}
    metadata = {"priority": "high", "requester": "user_123"}

    job_id, is_new = job_repo.create_job_idempotent(
        job_type=job_type,
        idempotency_key=idempotency_key,
        input_json=input_json,
        metadata=metadata,
    )

    assert is_new is True

    # Verify metadata is stored
    job = job_repo.get_job(job_id)
    assert job is not None
    assert job.metadata == metadata
