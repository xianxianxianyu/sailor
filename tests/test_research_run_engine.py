"""Tests for ResearchRunEngine and ResearchRunHandler

Tests cover:
- Engine delta computation with baseline
- Engine no-baseline case (initial run)
- Engine empty delta (no changes)
- Engine error handling
- Handler execution with artifact storage
- Handler error handling
- End-to-end integration test
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from core.artifact.repository import ArtifactRepository
from core.models import Job
from core.paper.engine import ResearchRunEngine
from core.paper.handlers import ResearchRunHandler
from core.paper.repository import PaperRepository
from core.runner.handlers import RunContext
from core.storage.db import Database
from core.storage.job_repository import JobRepository


# ========== Fixtures ==========


@pytest.fixture
def engine_setup(tmp_path: Path):
    """Create engine with dependencies"""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    paper_repo = PaperRepository(db)
    engine = ResearchRunEngine(paper_repo)
    return engine, paper_repo


@pytest.fixture
def handler_setup(tmp_path: Path):
    """Create handler with dependencies"""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    job_repo = JobRepository(db)
    paper_repo = PaperRepository(db)
    artifact_repo = ArtifactRepository(db)
    engine = ResearchRunEngine(paper_repo)
    handler = ResearchRunHandler(paper_repo, artifact_repo, engine)

    job = Job(job_id="test_job", job_type="research_run")
    job_repo.create_job(job)
    ctx = RunContext(job_repo=job_repo, run_id="test_job", data_dir=tmp_path)

    return handler, ctx, paper_repo, artifact_repo, job_repo


# ========== Helper Functions ==========


def create_test_paper(paper_repo: PaperRepository, paper_id: str, title: str) -> str:
    """Create a test paper and return its paper_id"""
    from core.paper.models import PaperRecord

    record = PaperRecord(
        canonical_id=paper_id,
        canonical_url=f"https://arxiv.org/abs/{paper_id}",
        title=title,
        item_key=f"arxiv:{paper_id}",
        abstract=f"Abstract for {title}",
        published_at=datetime.utcnow(),
        authors=["Test Author"],
        venue="Test Venue",
        doi=None,
        pdf_url=None,
        external_ids={"arxiv": paper_id},
    )
    return paper_repo.upsert_paper(record)


# ========== Engine Tests ==========


def test_research_run_engine_with_baseline(engine_setup):
    """Test delta computation with baseline snapshot"""
    engine, paper_repo = engine_setup

    # Create research program
    program = paper_repo.upsert_research_program(
        name="Test Program",
        description="Test program for delta computation",
        source_ids=["arxiv"],
        filters={},
        enabled=True,
    )

    # Create test papers
    paper1_id = create_test_paper(paper_repo, "2401.00001", "Paper 1")
    paper2_id = create_test_paper(paper_repo, "2401.00002", "Paper 2")
    paper3_id = create_test_paper(paper_repo, "2401.00003", "Paper 3")
    paper4_id = create_test_paper(paper_repo, "2401.00004", "Paper 4")

    # Create baseline snapshot with 3 papers
    baseline_snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    paper_repo.add_research_snapshot_items(
        baseline_snapshot_id,
        [paper1_id, paper2_id, paper3_id],
    )

    # Create current snapshot with 3 papers (1 removed, 1 new, 2 kept)
    current_snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    paper_repo.add_research_snapshot_items(
        current_snapshot_id,
        [paper1_id, paper2_id, paper4_id],  # paper3 removed, paper4 new
    )

    # Run engine
    bundle = engine.run(
        program_id=program.program_id,
        snapshot_id=current_snapshot_id,
        baseline_snapshot_id=baseline_snapshot_id,
    )

    # Verify bundle structure
    assert bundle["bundle_id"].startswith("rb_")
    assert bundle["program_id"] == program.program_id
    assert bundle["snapshot_id"] == current_snapshot_id
    assert bundle["baseline_snapshot_id"] == baseline_snapshot_id

    # Verify delta
    delta = bundle["delta"]
    assert len(delta["new_items"]) == 1
    assert len(delta["removed_items"]) == 1
    assert len(delta["kept_items"]) == 2

    # Verify new item
    assert delta["new_items"][0]["item_key"] == "2401.00004"
    assert delta["new_items"][0]["title"] == "Paper 4"

    # Verify removed item
    assert delta["removed_items"][0]["item_key"] == "2401.00003"
    assert delta["removed_items"][0]["title"] == "Paper 3"

    # Verify kept items
    kept_keys = {item["item_key"] for item in delta["kept_items"]}
    assert "2401.00001" in kept_keys
    assert "2401.00002" in kept_keys

    # Verify metadata
    metadata = bundle["metadata"]
    assert metadata["engine_version"] == "v1"
    assert metadata["new_count"] == 1
    assert metadata["removed_count"] == 1
    assert metadata["kept_count"] == 2
    assert "generated_at" in metadata


def test_research_run_engine_no_baseline(engine_setup):
    """Test delta computation without baseline (initial run)"""
    engine, paper_repo = engine_setup

    # Create research program
    program = paper_repo.upsert_research_program(
        name="Initial Program",
        description="Test program for initial run",
        source_ids=["arxiv"],
        filters={},
        enabled=True,
    )

    # Create test papers
    paper1_id = create_test_paper(paper_repo, "2402.00001", "Initial Paper 1")
    paper2_id = create_test_paper(paper_repo, "2402.00002", "Initial Paper 2")

    # Create snapshot with 2 papers
    snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    paper_repo.add_research_snapshot_items(
        snapshot_id,
        [paper1_id, paper2_id],
    )

    # Run engine without baseline
    bundle = engine.run(
        program_id=program.program_id,
        snapshot_id=snapshot_id,
        baseline_snapshot_id=None,
    )

    # Verify bundle structure
    assert bundle["bundle_id"].startswith("rb_")
    assert bundle["program_id"] == program.program_id
    assert bundle["snapshot_id"] == snapshot_id
    assert bundle["baseline_snapshot_id"] is None

    # Verify delta - all items should be "new"
    delta = bundle["delta"]
    assert len(delta["new_items"]) == 2
    assert len(delta["removed_items"]) == 0
    assert len(delta["kept_items"]) == 0

    # Verify metadata
    metadata = bundle["metadata"]
    assert metadata["new_count"] == 2
    assert metadata["removed_count"] == 0
    assert metadata["kept_count"] == 0


def test_research_run_engine_empty_delta(engine_setup):
    """Test delta computation with no changes between snapshots"""
    engine, paper_repo = engine_setup

    # Create research program
    program = paper_repo.upsert_research_program(
        name="Stable Program",
        description="Test program with no changes",
        source_ids=["arxiv"],
        filters={},
        enabled=True,
    )

    # Create test papers
    paper1_id = create_test_paper(paper_repo, "2403.00001", "Stable Paper 1")
    paper2_id = create_test_paper(paper_repo, "2403.00002", "Stable Paper 2")

    # Create baseline snapshot
    baseline_snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    paper_repo.add_research_snapshot_items(
        baseline_snapshot_id,
        [paper1_id, paper2_id],
    )

    # Create current snapshot with same papers
    current_snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    paper_repo.add_research_snapshot_items(
        current_snapshot_id,
        [paper1_id, paper2_id],
    )

    # Run engine
    bundle = engine.run(
        program_id=program.program_id,
        snapshot_id=current_snapshot_id,
        baseline_snapshot_id=baseline_snapshot_id,
    )

    # Verify delta - no new or removed items
    delta = bundle["delta"]
    assert len(delta["new_items"]) == 0
    assert len(delta["removed_items"]) == 0
    assert len(delta["kept_items"]) == 2

    # Verify metadata
    metadata = bundle["metadata"]
    assert metadata["new_count"] == 0
    assert metadata["removed_count"] == 0
    assert metadata["kept_count"] == 2


def test_research_run_engine_snapshot_not_found(engine_setup):
    """Test error handling when snapshot not found"""
    engine, paper_repo = engine_setup

    # Create research program
    program = paper_repo.upsert_research_program(
        name="Error Program",
        description="Test program for error handling",
        source_ids=["arxiv"],
        filters={},
        enabled=True,
    )

    # Try to run with non-existent snapshot
    with pytest.raises(ValueError, match="Snapshot not found"):
        engine.run(
            program_id=program.program_id,
            snapshot_id="nonexistent_snapshot",
            baseline_snapshot_id=None,
        )


def test_research_run_engine_program_not_found(engine_setup):
    """Test error handling when program not found"""
    engine, paper_repo = engine_setup

    # Try to run with non-existent program
    with pytest.raises(ValueError, match="Research program not found"):
        engine.run(
            program_id="nonexistent_program",
            snapshot_id="some_snapshot",
            baseline_snapshot_id=None,
        )


def test_research_run_engine_disabled_program(engine_setup):
    """Test error handling when program is disabled"""
    engine, paper_repo = engine_setup

    # Create disabled program
    program = paper_repo.upsert_research_program(
        name="Disabled Program",
        description="Test disabled program",
        source_ids=["arxiv"],
        filters={},
        enabled=False,
    )

    # Create snapshot
    snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )

    # Try to run with disabled program
    with pytest.raises(ValueError, match="Research program is disabled"):
        engine.run(
            program_id=program.program_id,
            snapshot_id=snapshot_id,
            baseline_snapshot_id=None,
        )


# ========== Handler Tests ==========


def test_research_run_handler_execution(handler_setup):
    """Test handler execution with artifact storage"""
    handler, ctx, paper_repo, artifact_repo, job_repo = handler_setup

    # Create research program
    program = paper_repo.upsert_research_program(
        name="Handler Test Program",
        description="Test program for handler",
        source_ids=["arxiv"],
        filters={},
        enabled=True,
    )

    # Create test papers
    paper1_id = create_test_paper(paper_repo, "2404.00001", "Handler Paper 1")
    paper2_id = create_test_paper(paper_repo, "2404.00002", "Handler Paper 2")

    # Create snapshot
    snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    paper_repo.add_research_snapshot_items(
        snapshot_id,
        [paper1_id, paper2_id],
    )

    # Create job
    job = Job(
        job_id="handler_test_job",
        job_type="research_run",
        input_json=json.dumps({
            "program_id": program.program_id,
            "snapshot_id": snapshot_id,
            "baseline_snapshot_id": None,
        }),
    )
    job_repo.create_job(job)

    # Execute handler
    output_json = handler.execute(job, ctx)
    output = json.loads(output_json)

    # Verify output
    assert "bundle_id" in output
    assert "artifact_id" in output
    assert output["bundle_id"].startswith("rb_")

    # Verify artifact was stored
    artifact = artifact_repo.get(output["artifact_id"])
    assert artifact is not None
    assert artifact.kind == "research_bundle"
    assert artifact.producer["engine"] == "ResearchRunEngine"

    # Verify artifact content
    bundle = artifact.content
    assert bundle["bundle_id"] == output["bundle_id"]
    assert bundle["program_id"] == program.program_id
    assert len(bundle["delta"]["new_items"]) == 2


def test_research_run_handler_program_not_found(handler_setup):
    """Test handler error handling when program not found"""
    handler, ctx, paper_repo, artifact_repo, job_repo = handler_setup

    # Create job with non-existent program
    job = Job(
        job_id="error_test_job",
        job_type="research_run",
        input_json=json.dumps({
            "program_id": "nonexistent_program",
            "snapshot_id": "some_snapshot",
            "baseline_snapshot_id": None,
        }),
    )
    job_repo.create_job(job)

    # Execute handler - should raise error
    with pytest.raises(ValueError, match="Research program not found"):
        handler.execute(job, ctx)


def test_research_run_handler_missing_snapshot_id(handler_setup):
    """Test handler error handling when snapshot_id is missing"""
    handler, ctx, paper_repo, artifact_repo, job_repo = handler_setup

    # Create job without snapshot_id
    job = Job(
        job_id="missing_snapshot_job",
        job_type="research_run",
        input_json=json.dumps({
            "program_id": "some_program",
        }),
    )
    job_repo.create_job(job)

    # Execute handler - should raise error
    with pytest.raises(ValueError, match="snapshot_id is required"):
        handler.execute(job, ctx)


# ========== Integration Test ==========


def test_research_run_e2e(tmp_path: Path):
    """End-to-end test of research run workflow"""
    # Setup
    db = Database(tmp_path / "test.db")
    db.init_schema()
    job_repo = JobRepository(db)
    paper_repo = PaperRepository(db)
    artifact_repo = ArtifactRepository(db)
    engine = ResearchRunEngine(paper_repo)
    handler = ResearchRunHandler(paper_repo, artifact_repo, engine)

    # Create research program
    program = paper_repo.upsert_research_program(
        name="E2E Test Program",
        description="End-to-end test program",
        source_ids=["arxiv"],
        filters={},
        enabled=True,
    )

    # Create test papers
    paper1_id = create_test_paper(paper_repo, "2405.00001", "E2E Paper 1")
    paper2_id = create_test_paper(paper_repo, "2405.00002", "E2E Paper 2")
    paper3_id = create_test_paper(paper_repo, "2405.00003", "E2E Paper 3")

    # Create baseline snapshot
    baseline_snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    paper_repo.add_research_snapshot_items(
        baseline_snapshot_id,
        [paper1_id, paper2_id],
    )

    # Create current snapshot
    current_snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    paper_repo.add_research_snapshot_items(
        current_snapshot_id,
        [paper2_id, paper3_id],  # paper1 removed, paper3 new, paper2 kept
    )

    # Create and execute job
    job = Job(
        job_id="e2e_test_job",
        job_type="research_run",
        input_json=json.dumps({
            "program_id": program.program_id,
            "snapshot_id": current_snapshot_id,
            "baseline_snapshot_id": baseline_snapshot_id,
        }),
    )
    job_repo.create_job(job)
    ctx = RunContext(job_repo=job_repo, run_id="e2e_test_job", data_dir=tmp_path)

    output_json = handler.execute(job, ctx)
    output = json.loads(output_json)

    # Verify complete workflow
    artifact = artifact_repo.get(output["artifact_id"])
    bundle = artifact.content

    assert len(bundle["delta"]["new_items"]) == 1
    assert len(bundle["delta"]["removed_items"]) == 1
    assert len(bundle["delta"]["kept_items"]) == 1

    assert bundle["delta"]["new_items"][0]["item_key"] == "2405.00003"
    assert bundle["delta"]["removed_items"][0]["item_key"] == "2405.00001"
    assert bundle["delta"]["kept_items"][0]["item_key"] == "2405.00002"

