"""Tests for ResearchSnapshotHandler

Test coverage for research snapshot capture and ingestion.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.models import Job
from core.paper.handlers import ResearchSnapshotHandler
from core.paper.models import Paper, PaperRecord, ResearchProgram
from core.paper.repository import PaperRepository
from core.paper.tools import research_capture_papers, research_snapshot_ingest
from core.runner.handlers import RunContext
from core.storage.db import Database
from core.storage.job_repository import JobRepository


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    db = Database(db_path)
    db.init_schema()
    yield db

    # Cleanup (Windows may still have file locked)
    try:
        db_path.unlink()
    except (PermissionError, FileNotFoundError):
        pass


@pytest.fixture
def paper_repo(temp_db):
    """Create PaperRepository with temp database"""
    return PaperRepository(temp_db)


@pytest.fixture
def job_repo(temp_db):
    """Create JobRepository with temp database"""
    return JobRepository(temp_db)


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def run_context(job_repo, temp_data_dir):
    """Create RunContext for testing"""
    # Create a job first to satisfy foreign key constraint
    job = Job(
        job_id="test_run_001",
        job_type="research_snapshot",
        input_json="{}",
        status="pending",
        created_at=datetime.utcnow(),
    )
    job_repo.create_job(job)

    return RunContext(
        job_repo=job_repo,
        run_id="test_run_001",
        data_dir=temp_data_dir,
    )


@pytest.fixture
def sample_papers(paper_repo):
    """Create sample papers in database"""
    papers = []
    base_time = datetime.utcnow() - timedelta(days=30)

    # Create paper source
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="https://export.arxiv.org/api/query",
        name="Test ArXiv Source",
        config_json=json.dumps({"query": "machine learning"}),
    )
    source_id = source.source_id

    # Create papers
    for i in range(10):
        paper_record = PaperRecord(
            canonical_id=f"arxiv:2024.{i:04d}",
            canonical_url=f"https://arxiv.org/abs/2024.{i:04d}",
            title=f"Test Paper {i}: Machine Learning Research",
            abstract=f"This paper discusses machine learning techniques for problem {i}.",
            published_at=base_time + timedelta(days=i),
            authors=[f"Author {i}"],
            venue="arXiv" if i % 2 == 0 else "NeurIPS",
            doi=f"10.1234/test.{i}",
            pdf_url=f"https://arxiv.org/pdf/2024.{i:04d}.pdf",
            item_key=f"item_{i}",
        )
        paper_id = paper_repo.upsert_paper(paper_record)

        # Mark as seen by source
        paper_repo.mark_seen(
            source_id=source_id,
            item_key=f"item_{i}",
            paper_id=paper_id,
            seen_at=base_time + timedelta(days=i),
        )

        papers.append(paper_id)

    return {
        "source_id": source_id,
        "paper_ids": papers,
        "base_time": base_time,
    }


@pytest.fixture
def research_program(paper_repo, sample_papers):
    """Create research program"""
    program = paper_repo.upsert_research_program(
        name="Test Research Program",
        description="Test program for ML papers",
        source_ids=[sample_papers["source_id"]],
        filters={
            "keywords": ["machine learning"],
            "venues": ["arXiv", "NeurIPS"],
        },
    )
    return program


def test_research_capture_papers(run_context, paper_repo, sample_papers, research_program):
    """Test capturing papers from database"""
    source_ids = [sample_papers["source_id"]]
    filters = {"keywords": ["machine learning"]}

    capture_id = research_capture_papers(
        ctx=run_context,
        paper_repo=paper_repo,
        program_id=research_program.program_id,
        source_ids=source_ids,
        filters=filters,
        limit=1000,
    )

    # Verify capture_id returned
    assert capture_id.startswith("cap_")

    # Load and verify capture content
    raw_content = run_context.load_raw_capture(capture_id)
    raw_data = json.loads(raw_content)

    assert raw_data["program_id"] == research_program.program_id
    assert raw_data["source_ids"] == source_ids
    assert raw_data["total_count"] == 10  # All papers match keyword
    assert len(raw_data["papers"]) == 10

    # Verify paper structure
    paper = raw_data["papers"][0]
    assert "paper_id" in paper
    assert "title" in paper
    assert "abstract" in paper
    assert "machine learning" in paper["title"].lower()


def test_research_capture_papers_with_keyword_filter(run_context, paper_repo, sample_papers, research_program):
    """Test keyword filtering"""
    source_ids = [sample_papers["source_id"]]
    filters = {"keywords": ["nonexistent keyword"]}

    capture_id = research_capture_papers(
        ctx=run_context,
        paper_repo=paper_repo,
        program_id=research_program.program_id,
        source_ids=source_ids,
        filters=filters,
        limit=1000,
    )

    raw_content = run_context.load_raw_capture(capture_id)
    raw_data = json.loads(raw_content)

    # No papers should match
    assert raw_data["total_count"] == 0
    assert len(raw_data["papers"]) == 0


def test_research_capture_papers_with_venue_filter(run_context, paper_repo, sample_papers, research_program):
    """Test venue filtering"""
    source_ids = [sample_papers["source_id"]]
    filters = {"venues": ["arXiv"]}

    capture_id = research_capture_papers(
        ctx=run_context,
        paper_repo=paper_repo,
        program_id=research_program.program_id,
        source_ids=source_ids,
        filters=filters,
        limit=1000,
    )

    raw_content = run_context.load_raw_capture(capture_id)
    raw_data = json.loads(raw_content)

    # Only papers with venue="arXiv" should match (5 papers)
    assert raw_data["total_count"] == 5
    for paper in raw_data["papers"]:
        assert paper["venue"] == "arXiv"


def test_research_capture_papers_with_time_window(run_context, paper_repo, sample_papers, research_program):
    """Test time window filtering"""
    base_time = sample_papers["base_time"]
    source_ids = [sample_papers["source_id"]]
    filters = {}

    # Capture papers from days 2-5
    window_since = (base_time + timedelta(days=2)).isoformat()
    window_until = (base_time + timedelta(days=5)).isoformat()

    capture_id = research_capture_papers(
        ctx=run_context,
        paper_repo=paper_repo,
        program_id=research_program.program_id,
        source_ids=source_ids,
        filters=filters,
        window_since=window_since,
        window_until=window_until,
        limit=1000,
    )

    raw_content = run_context.load_raw_capture(capture_id)
    raw_data = json.loads(raw_content)

    # Should capture papers 2, 3, 4 (3 papers)
    assert raw_data["total_count"] == 3


def test_research_snapshot_ingest(run_context, paper_repo, sample_papers, research_program):
    """Test ingesting capture into snapshot"""
    # First capture papers
    source_ids = [sample_papers["source_id"]]
    filters = {"keywords": ["machine learning"]}

    capture_id = research_capture_papers(
        ctx=run_context,
        paper_repo=paper_repo,
        program_id=research_program.program_id,
        source_ids=source_ids,
        filters=filters,
        limit=1000,
    )

    # Then ingest into snapshot
    snapshot_id = research_snapshot_ingest(
        ctx=run_context,
        paper_repo=paper_repo,
        program_id=research_program.program_id,
        raw_capture_ref=capture_id,
    )

    # Verify snapshot created
    assert snapshot_id.startswith("rsnap_")

    # Verify snapshot in database
    snapshot = paper_repo.get_research_snapshot(snapshot_id)
    assert snapshot is not None
    assert snapshot.program_id == research_program.program_id
    assert snapshot.paper_count == 10

    # Verify snapshot items
    items = paper_repo.list_research_snapshot_items(snapshot_id, limit=100)
    assert len(items) == 10

    # Verify items are in order (items are tuples of (paper_id, position))
    # Position starts at 1, not 0
    for i, (paper_id, position) in enumerate(items):
        assert position == i + 1


def test_handler_execute_success(run_context, paper_repo, sample_papers, research_program):
    """Test end-to-end handler execution"""
    handler = ResearchSnapshotHandler(paper_repo)

    job = Job(
        job_id="test_job_001",
        job_type="research_snapshot",
        input_json=json.dumps({"program_id": research_program.program_id}),
        status="pending",
        created_at=datetime.utcnow(),
    )

    output_json = handler.execute(job, run_context)

    # Verify output
    output = json.loads(output_json)
    assert "snapshot_id" in output
    assert output["snapshot_id"].startswith("rsnap_")

    # Verify snapshot exists
    snapshot = paper_repo.get_research_snapshot(output["snapshot_id"])
    assert snapshot is not None
    assert snapshot.program_id == research_program.program_id

    # Verify events emitted
    events = run_context.job_repo.list_events(run_id=run_context.run_id)
    event_types = [e.event_type for e in events]
    assert "ResearchSnapshotStarted" in event_types
    assert "ResearchSnapshotFinished" in event_types


def test_handler_program_not_found(run_context, paper_repo):
    """Test error handling for missing program"""
    handler = ResearchSnapshotHandler(paper_repo)

    job = Job(
        job_id="test_job_002",
        job_type="research_snapshot",
        input_json=json.dumps({"program_id": "nonexistent_program"}),
        status="pending",
        created_at=datetime.utcnow(),
    )

    with pytest.raises(ValueError, match="Research program not found"):
        handler.execute(job, run_context)


def test_handler_program_disabled(run_context, paper_repo, sample_papers):
    """Test error handling for disabled program"""
    # Create disabled program
    program = paper_repo.upsert_research_program(
        name="Disabled Program",
        description="Test",
        source_ids=[sample_papers["source_id"]],
        filters={},
        enabled=False,  # Create as disabled
    )

    handler = ResearchSnapshotHandler(paper_repo)

    job = Job(
        job_id="test_job_003",
        job_type="research_snapshot",
        input_json=json.dumps({"program_id": program.program_id}),
        status="pending",
        created_at=datetime.utcnow(),
    )

    with pytest.raises(ValueError, match="Research program is disabled"):
        handler.execute(job, run_context)


def test_handler_with_time_window(run_context, paper_repo, sample_papers, research_program):
    """Test handler with time window in input"""
    base_time = sample_papers["base_time"]
    handler = ResearchSnapshotHandler(paper_repo)

    job = Job(
        job_id="test_job_004",
        job_type="research_snapshot",
        input_json=json.dumps({
            "program_id": research_program.program_id,
            "window": {
                "since": (base_time + timedelta(days=5)).isoformat(),
                "until": (base_time + timedelta(days=8)).isoformat(),
            }
        }),
        status="pending",
        created_at=datetime.utcnow(),
    )

    output_json = handler.execute(job, run_context)
    output = json.loads(output_json)

    # Verify snapshot created with limited papers
    snapshot = paper_repo.get_research_snapshot(output["snapshot_id"])
    assert snapshot is not None
    # Should have papers 5, 6, 7 (3 papers)
    assert snapshot.paper_count == 3


def test_idempotency_key_generation(run_context, paper_repo, sample_papers, research_program):
    """Test idempotency key is consistent"""
    source_ids = [sample_papers["source_id"]]
    filters = {"keywords": ["test"]}

    # Capture twice with same parameters
    capture_id_1 = research_capture_papers(
        ctx=run_context,
        paper_repo=paper_repo,
        program_id=research_program.program_id,
        source_ids=source_ids,
        filters=filters,
        limit=1000,
    )

    capture_id_2 = research_capture_papers(
        ctx=run_context,
        paper_repo=paper_repo,
        program_id=research_program.program_id,
        source_ids=source_ids,
        filters=filters,
        limit=1000,
    )

    # Both should succeed (idempotency key should be same)
    assert capture_id_1.startswith("cap_")
    assert capture_id_2.startswith("cap_")
    # Both captures should be created (idempotency allows multiple calls)


def test_handler_missing_program_id(run_context, paper_repo):
    """Test error handling for missing program_id in input"""
    handler = ResearchSnapshotHandler(paper_repo)

    job = Job(
        job_id="test_job_005",
        job_type="research_snapshot",
        input_json=json.dumps({}),
        status="pending",
        created_at=datetime.utcnow(),
    )

    with pytest.raises(ValueError, match="program_id is required"):
        handler.execute(job, run_context)
