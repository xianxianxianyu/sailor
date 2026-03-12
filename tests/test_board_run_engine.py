"""Tests for BoardRunEngine and BoardRunHandler

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
from core.board.engine import BoardRunEngine
from core.board.handlers import BoardRunHandler
from core.board.repository import BoardRepository
from core.models import Job
from core.runner.handlers import RunContext
from core.storage.db import Database
from core.storage.job_repository import JobRepository


# ========== Fixtures ==========


@pytest.fixture
def engine_setup(tmp_path: Path):
    """Create engine with dependencies"""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    board_repo = BoardRepository(db)
    engine = BoardRunEngine(board_repo)
    return engine, board_repo


@pytest.fixture
def handler_setup(tmp_path: Path):
    """Create handler with dependencies"""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    job_repo = JobRepository(db)
    board_repo = BoardRepository(db)
    artifact_repo = ArtifactRepository(db)
    engine = BoardRunEngine(board_repo)
    handler = BoardRunHandler(board_repo, artifact_repo, engine)

    job = Job(job_id="test_job", job_type="board_run")
    job_repo.create_job(job)
    ctx = RunContext(job_repo=job_repo, run_id="test_job", data_dir=tmp_path)

    return handler, ctx, board_repo, artifact_repo, job_repo


# ========== Engine Tests ==========


def test_board_run_engine_with_baseline(engine_setup):
    """Test delta computation with baseline snapshot"""
    engine, board_repo = engine_setup

    # Create board
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({"language": "python"}),
    )

    # Create baseline snapshot with 3 items
    baseline_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        baseline_snapshot_id,
        [
            {
                "item_key": "v1:github_repo:owner1/repo1",
                "source_order": 1,
                "title": "Repo 1",
                "url": "https://github.com/owner1/repo1",
                "meta_json": json.dumps({"stars": 100}),
            },
            {
                "item_key": "v1:github_repo:owner2/repo2",
                "source_order": 2,
                "title": "Repo 2",
                "url": "https://github.com/owner2/repo2",
                "meta_json": json.dumps({"stars": 200}),
            },
            {
                "item_key": "v1:github_repo:owner3/repo3",
                "source_order": 3,
                "title": "Repo 3",
                "url": "https://github.com/owner3/repo3",
                "meta_json": json.dumps({"stars": 300}),
            },
        ],
    )

    # Create current snapshot with 4 items (1 removed, 1 new, 2 kept)
    current_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        current_snapshot_id,
        [
            {
                "item_key": "v1:github_repo:owner1/repo1",  # kept
                "source_order": 1,
                "title": "Repo 1",
                "url": "https://github.com/owner1/repo1",
                "meta_json": json.dumps({"stars": 150}),
            },
            {
                "item_key": "v1:github_repo:owner2/repo2",  # kept
                "source_order": 2,
                "title": "Repo 2",
                "url": "https://github.com/owner2/repo2",
                "meta_json": json.dumps({"stars": 250}),
            },
            # repo3 removed
            {
                "item_key": "v1:github_repo:owner4/repo4",  # new
                "source_order": 4,
                "title": "Repo 4",
                "url": "https://github.com/owner4/repo4",
                "meta_json": json.dumps({"stars": 400}),
            },
        ],
    )

    # Run engine
    bundle = engine.run(
        board_id=board.board_id,
        snapshot_id=current_snapshot_id,
        baseline_snapshot_id=baseline_snapshot_id,
    )

    # Verify bundle structure
    assert bundle["bundle_id"].startswith("bb_")
    assert bundle["board_id"] == board.board_id
    assert bundle["snapshot_id"] == current_snapshot_id
    assert bundle["baseline_snapshot_id"] == baseline_snapshot_id

    # Verify delta
    delta = bundle["delta"]
    assert len(delta["new_items"]) == 1
    assert len(delta["removed_items"]) == 1
    assert len(delta["kept_items"]) == 2

    # Verify new item
    assert delta["new_items"][0]["item_key"] == "v1:github_repo:owner4/repo4"
    assert delta["new_items"][0]["title"] == "Repo 4"
    assert delta["new_items"][0]["meta"]["stars"] == 400

    # Verify removed item
    assert delta["removed_items"][0]["item_key"] == "v1:github_repo:owner3/repo3"
    assert delta["removed_items"][0]["title"] == "Repo 3"

    # Verify kept items
    kept_keys = {item["item_key"] for item in delta["kept_items"]}
    assert "v1:github_repo:owner1/repo1" in kept_keys
    assert "v1:github_repo:owner2/repo2" in kept_keys

    # Verify metadata
    metadata = bundle["metadata"]
    assert metadata["engine_version"] == "v1"
    assert metadata["new_count"] == 1
    assert metadata["removed_count"] == 1
    assert metadata["kept_count"] == 2
    assert "generated_at" in metadata


def test_board_run_engine_no_baseline(engine_setup):
    """Test delta computation without baseline (initial run)"""
    engine, board_repo = engine_setup

    # Create board
    board = board_repo.upsert_board(
        provider="huggingface",
        kind="models",
        name="trending",
        config_json=json.dumps({}),
    )

    # Create snapshot with 2 items
    snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        snapshot_id,
        [
            {
                "item_key": "v1:hf_model:model1",
                "source_order": 1,
                "title": "Model 1",
                "url": "https://huggingface.co/model1",
                "meta_json": json.dumps({"likes": 50}),
            },
            {
                "item_key": "v1:hf_model:model2",
                "source_order": 2,
                "title": "Model 2",
                "url": "https://huggingface.co/model2",
                "meta_json": json.dumps({"likes": 100}),
            },
        ],
    )

    # Run engine without baseline
    bundle = engine.run(
        board_id=board.board_id,
        snapshot_id=snapshot_id,
        baseline_snapshot_id=None,
    )

    # Verify bundle structure
    assert bundle["bundle_id"].startswith("bb_")
    assert bundle["board_id"] == board.board_id
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


def test_board_run_engine_empty_delta(engine_setup):
    """Test delta computation with no changes"""
    engine, board_repo = engine_setup

    # Create board
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="rust",
        config_json=json.dumps({"language": "rust"}),
    )

    # Create baseline snapshot
    baseline_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    items = [
        {
            "item_key": "v1:github_repo:owner1/repo1",
            "source_order": 1,
            "title": "Repo 1",
            "url": "https://github.com/owner1/repo1",
            "meta_json": json.dumps({"stars": 100}),
        },
    ]
    board_repo.add_snapshot_items(baseline_snapshot_id, items)

    # Create current snapshot with same items
    current_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(current_snapshot_id, items)

    # Run engine
    bundle = engine.run(
        board_id=board.board_id,
        snapshot_id=current_snapshot_id,
        baseline_snapshot_id=baseline_snapshot_id,
    )

    # Verify delta - no changes
    delta = bundle["delta"]
    assert len(delta["new_items"]) == 0
    assert len(delta["removed_items"]) == 0
    assert len(delta["kept_items"]) == 1

    # Verify metadata
    metadata = bundle["metadata"]
    assert metadata["new_count"] == 0
    assert metadata["removed_count"] == 0
    assert metadata["kept_count"] == 1


def test_board_run_engine_snapshot_not_found(engine_setup):
    """Test error handling for non-existent snapshot"""
    engine, board_repo = engine_setup

    # Create board
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({}),
    )

    # Try to run with non-existent snapshot
    with pytest.raises(ValueError, match="Snapshot not found"):
        engine.run(
            board_id=board.board_id,
            snapshot_id="snap_nonexistent",
            baseline_snapshot_id=None,
        )


def test_item_key_stability(engine_setup):
    """Test item_key comparison stability across snapshots"""
    engine, board_repo = engine_setup

    # Create board
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="test",
        config_json=json.dumps({}),
    )

    # Create baseline with GitHub repos
    baseline_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        baseline_snapshot_id,
        [
            {
                "item_key": "v1:github_repo:owner/repo",
                "source_order": 1,
                "title": "Old Title",  # Title changed
                "url": "https://github.com/owner/repo",
                "meta_json": json.dumps({"stars": 100}),
            },
        ],
    )

    # Create current with same item_key but different title/meta
    current_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        current_snapshot_id,
        [
            {
                "item_key": "v1:github_repo:owner/repo",  # Same key
                "source_order": 1,
                "title": "New Title",  # Different title
                "url": "https://github.com/owner/repo",
                "meta_json": json.dumps({"stars": 200}),  # Different stars
            },
        ],
    )

    # Run engine
    bundle = engine.run(
        board_id=board.board_id,
        snapshot_id=current_snapshot_id,
        baseline_snapshot_id=baseline_snapshot_id,
    )

    # Verify item is kept (not new/removed) despite title/meta changes
    delta = bundle["delta"]
    assert len(delta["new_items"]) == 0
    assert len(delta["removed_items"]) == 0
    assert len(delta["kept_items"]) == 1
    assert delta["kept_items"][0]["item_key"] == "v1:github_repo:owner/repo"
    assert delta["kept_items"][0]["title"] == "New Title"  # Uses current title


# ========== Handler Tests ==========


def test_board_run_handler_execution(handler_setup):
    """Test handler execution with artifact storage"""
    handler, ctx, board_repo, artifact_repo, job_repo = handler_setup

    # Create board and snapshots
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({}),
    )

    baseline_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        baseline_snapshot_id,
        [
            {
                "item_key": "v1:github_repo:owner1/repo1",
                "source_order": 1,
                "title": "Repo 1",
                "url": "https://github.com/owner1/repo1",
                "meta_json": json.dumps({"stars": 100}),
            },
        ],
    )

    current_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        current_snapshot_id,
        [
            {
                "item_key": "v1:github_repo:owner2/repo2",
                "source_order": 1,
                "title": "Repo 2",
                "url": "https://github.com/owner2/repo2",
                "meta_json": json.dumps({"stars": 200}),
            },
        ],
    )

    # Create job
    job = Job(
        job_id="test_job",
        job_type="board_run",
        input_json=json.dumps({
            "board_id": board.board_id,
            "snapshot_id": current_snapshot_id,
            "baseline_snapshot_id": baseline_snapshot_id,
        }),
    )

    # Execute handler
    output_json = handler.execute(job, ctx)
    output = json.loads(output_json)

    # Verify output
    assert "bundle_id" in output
    assert "artifact_id" in output
    assert output["bundle_id"].startswith("bb_")
    assert output["artifact_id"].startswith("art_")

    # Verify artifact stored
    artifact = artifact_repo.get(output["artifact_id"])
    assert artifact is not None
    assert artifact.kind == "board_bundle"
    assert artifact.schema_version == "v1"
    assert artifact.producer["engine"] == "BoardRunEngine"
    assert artifact.producer["engine_version"] == "v1"
    assert artifact.job_id == "test_job"

    # Verify artifact content
    content = artifact.content
    assert content["bundle_id"] == output["bundle_id"]
    assert content["board_id"] == board.board_id
    assert len(content["delta"]["new_items"]) == 1
    assert len(content["delta"]["removed_items"]) == 1
    assert len(content["delta"]["kept_items"]) == 0

    # Verify input_refs
    assert artifact.input_refs["snapshot_id"] == current_snapshot_id
    assert artifact.input_refs["baseline_snapshot_id"] == baseline_snapshot_id

    # Verify metadata
    assert artifact.metadata["board_id"] == board.board_id
    assert artifact.metadata["new_count"] == 1
    assert artifact.metadata["removed_count"] == 1
    assert artifact.metadata["kept_count"] == 0

    # Verify events emitted
    events = job_repo.list_events(run_id="test_job")
    event_types = [e.event_type for e in events]
    assert "BoardRunStarted" in event_types
    assert "BoardRunFinished" in event_types


def test_board_run_handler_board_not_found(handler_setup):
    """Test handler error handling for non-existent board"""
    handler, ctx, board_repo, artifact_repo, job_repo = handler_setup

    # Create job with non-existent board
    job = Job(
        job_id="test_job",
        job_type="board_run",
        input_json=json.dumps({
            "board_id": "board_nonexistent",
            "snapshot_id": "snap_test",
        }),
    )

    # Execute handler - should raise ValueError
    with pytest.raises(ValueError, match="Board not found"):
        handler.execute(job, ctx)


# ========== Integration Test ==========


def test_board_run_e2e(tmp_path: Path):
    """End-to-end test of board run workflow"""
    # Setup
    db = Database(tmp_path / "test.db")
    db.init_schema()
    board_repo = BoardRepository(db)
    artifact_repo = ArtifactRepository(db)
    job_repo = JobRepository(db)
    engine = BoardRunEngine(board_repo)

    # Create board
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({"language": "python"}),
    )

    # Create two snapshots with different items
    baseline_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        baseline_snapshot_id,
        [
            {
                "item_key": "v1:github_repo:owner1/repo1",
                "source_order": 1,
                "title": "Repo 1",
                "url": "https://github.com/owner1/repo1",
                "meta_json": json.dumps({"stars": 100}),
            },
            {
                "item_key": "v1:github_repo:owner2/repo2",
                "source_order": 2,
                "title": "Repo 2",
                "url": "https://github.com/owner2/repo2",
                "meta_json": json.dumps({"stars": 200}),
            },
        ],
    )

    current_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(
        current_snapshot_id,
        [
            {
                "item_key": "v1:github_repo:owner2/repo2",  # kept
                "source_order": 1,
                "title": "Repo 2",
                "url": "https://github.com/owner2/repo2",
                "meta_json": json.dumps({"stars": 250}),
            },
            {
                "item_key": "v1:github_repo:owner3/repo3",  # new
                "source_order": 2,
                "title": "Repo 3",
                "url": "https://github.com/owner3/repo3",
                "meta_json": json.dumps({"stars": 300}),
            },
        ],
    )

    # Run engine
    bundle = engine.run(
        board_id=board.board_id,
        snapshot_id=current_snapshot_id,
        baseline_snapshot_id=baseline_snapshot_id,
    )

    # Verify delta computed correctly
    assert len(bundle["delta"]["new_items"]) == 1
    assert len(bundle["delta"]["removed_items"]) == 1
    assert len(bundle["delta"]["kept_items"]) == 1

    # Verify new item
    new_item = bundle["delta"]["new_items"][0]
    assert new_item["item_key"] == "v1:github_repo:owner3/repo3"
    assert new_item["title"] == "Repo 3"
    assert new_item["meta"]["stars"] == 300

    # Verify removed item
    removed_item = bundle["delta"]["removed_items"][0]
    assert removed_item["item_key"] == "v1:github_repo:owner1/repo1"
    assert removed_item["title"] == "Repo 1"

    # Verify kept item
    kept_item = bundle["delta"]["kept_items"][0]
    assert kept_item["item_key"] == "v1:github_repo:owner2/repo2"
    assert kept_item["title"] == "Repo 2"

    # Verify bundle structure
    assert bundle["bundle_id"].startswith("bb_")
    assert bundle["board_id"] == board.board_id
    assert bundle["snapshot_id"] == current_snapshot_id
    assert bundle["baseline_snapshot_id"] == baseline_snapshot_id
    assert bundle["metadata"]["engine_version"] == "v1"
    assert bundle["metadata"]["new_count"] == 1
    assert bundle["metadata"]["removed_count"] == 1
    assert bundle["metadata"]["kept_count"] == 1
