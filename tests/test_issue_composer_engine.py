"""Tests for IssueComposerEngine and IssueComposeHandler

Tests cover:
- Engine composition with research and boards
- Engine boards-only composition
- Engine research-only composition
- Engine empty bundles
- Section ordering (boards before research)
- Board section item ordering (new before kept)
- Research section sorting (published_at DESC)
- Issue ID generation
- Handler execution with artifact storage
- Handler error handling (missing bundles)
- Handler error handling (invalid input)
- End-to-end integration test
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from core.artifact.repository import ArtifactRepository
from core.follow.composer import IssueComposerEngine
from core.follow.handlers import IssueComposeHandler
from core.follow.models import FollowSpec
from core.models import Job
from core.runner.handlers import RunContext
from core.storage.db import Database
from core.storage.job_repository import JobRepository


# ========== Fixtures ==========


@pytest.fixture
def engine_setup():
    """Create engine (no dependencies)"""
    engine = IssueComposerEngine()
    return engine


@pytest.fixture
def handler_setup(tmp_path: Path):
    """Create handler with dependencies"""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    job_repo = JobRepository(db)
    artifact_repo = ArtifactRepository(db)
    engine = IssueComposerEngine()
    handler = IssueComposeHandler(artifact_repo, engine)

    job = Job(job_id="test_job", job_type="issue_compose")
    job_repo.create_job(job)
    ctx = RunContext(job_repo=job_repo, run_id="test_job", data_dir=tmp_path)

    return handler, ctx, artifact_repo, job_repo


# ========== Test Data Helpers ==========


def create_board_bundle(board_id: str, new_items: list, kept_items: list) -> dict:
    """Create a BoardBundle dict for testing"""
    return {
        "bundle_id": f"bb_{board_id}",
        "board_id": board_id,
        "snapshot_id": f"snap_{board_id}",
        "baseline_snapshot_id": None,
        "delta": {
            "new_items": new_items,
            "removed_items": [],
            "kept_items": kept_items,
        },
        "metadata": {
            "engine_version": "v1",
            "generated_at": datetime.utcnow().isoformat(),
            "new_count": len(new_items),
            "removed_count": 0,
            "kept_count": len(kept_items),
        },
    }


def create_research_bundle(program_id: str, new_items: list, kept_items: list) -> dict:
    """Create a ResearchBundle dict for testing"""
    return {
        "bundle_id": f"rb_{program_id}",
        "program_id": program_id,
        "snapshot_id": f"snap_{program_id}",
        "baseline_snapshot_id": None,
        "delta": {
            "new_items": new_items,
            "removed_items": [],
            "kept_items": kept_items,
        },
        "metadata": {
            "engine_version": "v1",
            "generated_at": datetime.utcnow().isoformat(),
            "new_count": len(new_items),
            "removed_count": 0,
            "kept_count": len(kept_items),
        },
    }


# ========== Engine Tests ==========


def test_compose_with_research_and_boards(engine_setup):
    """Test full composition with research and board bundles"""
    engine = engine_setup

    # Create test data
    follow_spec = FollowSpec(
        follow_id="follow1",
        name="Test Follow",
        description="Test follow description",
    )

    window = {"since": "2024-01-01", "until": "2024-01-31"}

    board_bundle = create_board_bundle(
        "board1",
        new_items=[
            {
                "item_key": "v1:github_repo:owner1/repo1",
                "source_order": 1,
                "title": "New Repo 1",
                "url": "https://github.com/owner1/repo1",
                "meta": {"stars": 100},
            }
        ],
        kept_items=[
            {
                "item_key": "v1:github_repo:owner2/repo2",
                "source_order": 2,
                "title": "Kept Repo 2",
                "url": "https://github.com/owner2/repo2",
                "meta": {"stars": 200},
            }
        ],
    )

    research_bundle = create_research_bundle(
        "prog1",
        new_items=[
            {
                "item_key": "arxiv:2024.01234",
                "published_at": "2024-01-15T00:00:00",
                "title": "New Paper 1",
                "source_order": 1,
            }
        ],
        kept_items=[
            {
                "item_key": "arxiv:2024.01235",
                "published_at": "2024-01-10T00:00:00",
                "title": "Kept Paper 1",
                "source_order": 2,
            }
        ],
    )

    # Compose
    issue = engine.compose(
        follow_spec=follow_spec,
        window=window,
        research_bundle=research_bundle,
        board_bundles=[board_bundle],
    )

    # Verify structure
    assert issue["issue_id"].startswith("iss_")
    assert issue["follow_id"] == "follow1"
    assert issue["window"] == window
    assert issue["ordering_policy"] == "v1:default"
    assert len(issue["sections"]) == 2  # 1 board + 1 research

    # Verify board section comes first
    board_section = issue["sections"][0]
    assert board_section["section_id"] == "board.board1"
    assert len(board_section["items"]) == 2  # 1 new + 1 kept
    assert board_section["metadata"]["new_count"] == 1
    assert board_section["metadata"]["kept_count"] == 1

    # Verify research section comes second
    research_section = issue["sections"][1]
    assert research_section["section_id"] == "research.prog1"
    assert len(research_section["items"]) == 2  # 1 new + 1 kept
    assert research_section["metadata"]["new_count"] == 1
    assert research_section["metadata"]["kept_count"] == 1

    # Verify metadata
    assert issue["metadata"]["total_items"] == 4
    assert issue["metadata"]["section_count"] == 2
    assert issue["metadata"]["engine_version"] == "v1"


def test_compose_boards_only(engine_setup):
    """Test composition with only board bundles (no research)"""
    engine = engine_setup

    follow_spec = FollowSpec(follow_id="follow1", name="Test Follow")
    window = {"since": "2024-01-01", "until": "2024-01-31"}

    board_bundle = create_board_bundle(
        "board1",
        new_items=[{"item_key": "key1", "source_order": 1, "title": "Item 1", "url": "http://example.com", "meta": {}}],
        kept_items=[],
    )

    # Compose without research
    issue = engine.compose(
        follow_spec=follow_spec,
        window=window,
        research_bundle=None,
        board_bundles=[board_bundle],
    )

    # Verify only board section
    assert len(issue["sections"]) == 1
    assert issue["sections"][0]["section_id"] == "board.board1"
    assert issue["input_refs"]["research_bundle_id"] is None
    assert len(issue["input_refs"]["board_bundle_ids"]) == 1


def test_compose_research_only(engine_setup):
    """Test composition with only research bundle (no boards)"""
    engine = engine_setup

    follow_spec = FollowSpec(follow_id="follow1", name="Test Follow")
    window = {"since": "2024-01-01", "until": "2024-01-31"}

    research_bundle = create_research_bundle(
        "prog1",
        new_items=[{"item_key": "arxiv:2024.01234", "published_at": "2024-01-15T00:00:00", "title": "Paper 1", "source_order": 1}],
        kept_items=[],
    )

    # Compose without boards
    issue = engine.compose(
        follow_spec=follow_spec,
        window=window,
        research_bundle=research_bundle,
        board_bundles=[],
    )

    # Verify only research section
    assert len(issue["sections"]) == 1
    assert issue["sections"][0]["section_id"] == "research.prog1"
    assert issue["input_refs"]["research_bundle_id"] == "rb_prog1"
    assert len(issue["input_refs"]["board_bundle_ids"]) == 0


def test_compose_empty_bundles(engine_setup):
    """Test composition with empty delta items"""
    engine = engine_setup

    follow_spec = FollowSpec(follow_id="follow1", name="Test Follow")
    window = {"since": "2024-01-01", "until": "2024-01-31"}

    # Empty board bundle
    board_bundle = create_board_bundle("board1", new_items=[], kept_items=[])

    # Empty research bundle
    research_bundle = create_research_bundle("prog1", new_items=[], kept_items=[])

    # Compose
    issue = engine.compose(
        follow_spec=follow_spec,
        window=window,
        research_bundle=research_bundle,
        board_bundles=[board_bundle],
    )

    # Verify empty sections
    assert len(issue["sections"]) == 2
    assert len(issue["sections"][0]["items"]) == 0
    assert len(issue["sections"][1]["items"]) == 0
    assert issue["metadata"]["total_items"] == 0


def test_section_ordering(engine_setup):
    """Test that board sections come before research sections"""
    engine = engine_setup

    follow_spec = FollowSpec(follow_id="follow1", name="Test Follow")
    window = {"since": "2024-01-01", "until": "2024-01-31"}

    # Create multiple board bundles
    board1 = create_board_bundle("board1", new_items=[{"item_key": "b1", "source_order": 1, "title": "B1", "url": "http://b1.com", "meta": {}}], kept_items=[])
    board2 = create_board_bundle("board2", new_items=[{"item_key": "b2", "source_order": 1, "title": "B2", "url": "http://b2.com", "meta": {}}], kept_items=[])

    # Create research bundle
    research = create_research_bundle("prog1", new_items=[{"item_key": "r1", "published_at": "2024-01-15T00:00:00", "title": "R1", "source_order": 1}], kept_items=[])

    # Compose
    issue = engine.compose(
        follow_spec=follow_spec,
        window=window,
        research_bundle=research,
        board_bundles=[board1, board2],
    )

    # Verify ordering: boards first, research last
    assert len(issue["sections"]) == 3
    assert issue["sections"][0]["section_id"] == "board.board1"
    assert issue["sections"][1]["section_id"] == "board.board2"
    assert issue["sections"][2]["section_id"] == "research.prog1"


def test_board_section_item_ordering(engine_setup):
    """Test that board section orders new_items before kept_items"""
    engine = engine_setup

    follow_spec = FollowSpec(follow_id="follow1", name="Test Follow")
    window = {"since": "2024-01-01", "until": "2024-01-31"}

    # Create board bundle with new and kept items
    board_bundle = create_board_bundle(
        "board1",
        new_items=[
            {"item_key": "new1", "source_order": 10, "title": "New 1", "url": "http://new1.com", "meta": {}},
            {"item_key": "new2", "source_order": 20, "title": "New 2", "url": "http://new2.com", "meta": {}},
        ],
        kept_items=[
            {"item_key": "kept1", "source_order": 5, "title": "Kept 1", "url": "http://kept1.com", "meta": {}},
            {"item_key": "kept2", "source_order": 15, "title": "Kept 2", "url": "http://kept2.com", "meta": {}},
        ],
    )

    # Compose
    issue = engine.compose(
        follow_spec=follow_spec,
        window=window,
        research_bundle=None,
        board_bundles=[board_bundle],
    )

    # Verify ordering: new items first, then kept items
    section = issue["sections"][0]
    items = section["items"]
    assert len(items) == 4
    assert items[0]["item_key"] == "new1"  # new items first
    assert items[1]["item_key"] == "new2"
    assert items[2]["item_key"] == "kept1"  # kept items second
    assert items[3]["item_key"] == "kept2"


def test_research_section_sorting(engine_setup):
    """Test that research section sorts by published_at DESC"""
    engine = engine_setup

    follow_spec = FollowSpec(follow_id="follow1", name="Test Follow")
    window = {"since": "2024-01-01", "until": "2024-01-31"}

    # Create research bundle with items in random order
    research_bundle = create_research_bundle(
        "prog1",
        new_items=[
            {"item_key": "paper2", "published_at": "2024-01-10T00:00:00", "title": "Paper 2", "source_order": 1},
            {"item_key": "paper3", "published_at": "2024-01-20T00:00:00", "title": "Paper 3", "source_order": 2},
        ],
        kept_items=[
            {"item_key": "paper1", "published_at": "2024-01-05T00:00:00", "title": "Paper 1", "source_order": 3},
            {"item_key": "paper4", "published_at": "2024-01-25T00:00:00", "title": "Paper 4", "source_order": 4},
        ],
    )

    # Compose
    issue = engine.compose(
        follow_spec=follow_spec,
        window=window,
        research_bundle=research_bundle,
        board_bundles=[],
    )

    # Verify sorting: published_at DESC
    section = issue["sections"][0]
    items = section["items"]
    assert len(items) == 4
    assert items[0]["item_key"] == "paper4"  # 2024-01-25 (newest)
    assert items[1]["item_key"] == "paper3"  # 2024-01-20
    assert items[2]["item_key"] == "paper2"  # 2024-01-10
    assert items[3]["item_key"] == "paper1"  # 2024-01-05 (oldest)


def test_issue_id_generation(engine_setup):
    """Test that unique issue IDs are generated"""
    engine = engine_setup

    follow_spec = FollowSpec(follow_id="follow1", name="Test Follow")
    window = {"since": "2024-01-01", "until": "2024-01-31"}

    # Compose twice
    issue1 = engine.compose(follow_spec, window, None, [])
    issue2 = engine.compose(follow_spec, window, None, [])

    # Verify unique IDs
    assert issue1["issue_id"] != issue2["issue_id"]
    assert issue1["issue_id"].startswith("iss_")
    assert issue2["issue_id"].startswith("iss_")


# ========== Handler Tests ==========


def test_handler_execution(handler_setup):
    """Test handler execution with artifact storage"""
    handler, ctx, artifact_repo, job_repo = handler_setup

    # Create test bundles and store as artifacts
    board_bundle = create_board_bundle(
        "board1",
        new_items=[{"item_key": "key1", "source_order": 1, "title": "Item 1", "url": "http://example.com", "meta": {}}],
        kept_items=[],
    )

    research_bundle = create_research_bundle(
        "prog1",
        new_items=[{"item_key": "arxiv:2024.01234", "published_at": "2024-01-15T00:00:00", "title": "Paper 1", "source_order": 1}],
        kept_items=[],
    )

    # Store bundles as artifacts
    board_artifact_id = artifact_repo.put(
        kind="board_bundle",
        schema_version="v1",
        content=board_bundle,
        producer_engine="BoardRunEngine",
        producer_version="v1",
        job_id="test_job",
    )

    research_artifact_id = artifact_repo.put(
        kind="research_bundle",
        schema_version="v1",
        content=research_bundle,
        producer_engine="ResearchRunEngine",
        producer_version="v1",
        job_id="test_job",
    )

    # Create job with input
    job = Job(
        job_id="compose_job",
        job_type="issue_compose",
        input_json=json.dumps({
            "follow_spec": {
                "follow_id": "follow1",
                "name": "Test Follow",
                "description": "Test description",
            },
            "window": {"since": "2024-01-01", "until": "2024-01-31"},
            "research_bundle_id": research_artifact_id,
            "board_bundle_ids": [board_artifact_id],
        }),
    )
    job_repo.create_job(job)

    # Execute handler
    output_json = handler.execute(job, ctx)
    output = json.loads(output_json)

    # Verify output
    assert "issue_id" in output
    assert "artifact_id" in output
    assert output["issue_id"].startswith("iss_")

    # Verify artifact was stored
    artifact = artifact_repo.get(output["artifact_id"])
    assert artifact is not None
    assert artifact.kind == "issue_snapshot"
    assert artifact.producer["engine"] == "IssueComposerEngine"

    # Verify artifact content
    issue = artifact.content
    assert issue["issue_id"] == output["issue_id"]
    assert issue["follow_id"] == "follow1"
    assert len(issue["sections"]) == 2


def test_handler_missing_bundle(handler_setup):
    """Test handler error when bundle not found"""
    handler, ctx, artifact_repo, job_repo = handler_setup

    # Create job with non-existent bundle ID
    job = Job(
        job_id="compose_job",
        job_type="issue_compose",
        input_json=json.dumps({
            "follow_spec": {
                "follow_id": "follow1",
                "name": "Test Follow",
            },
            "window": {"since": "2024-01-01", "until": "2024-01-31"},
            "research_bundle_id": "art_nonexistent",
            "board_bundle_ids": [],
        }),
    )
    job_repo.create_job(job)

    # Execute should raise error
    with pytest.raises(ValueError, match="Research bundle not found"):
        handler.execute(job, ctx)


def test_handler_invalid_input(handler_setup):
    """Test handler error with invalid input"""
    handler, ctx, artifact_repo, job_repo = handler_setup

    # Create job with missing follow_spec
    job = Job(
        job_id="compose_job",
        job_type="issue_compose",
        input_json=json.dumps({
            "window": {"since": "2024-01-01", "until": "2024-01-31"},
        }),
    )
    job_repo.create_job(job)

    # Execute should raise error
    with pytest.raises(ValueError, match="follow_spec is required"):
        handler.execute(job, ctx)


# ========== Integration Test ==========


def test_issue_compose_e2e(handler_setup):
    """End-to-end test: create bundles, compose, verify artifact"""
    handler, ctx, artifact_repo, job_repo = handler_setup

    # Create multiple board bundles
    board1 = create_board_bundle(
        "board1",
        new_items=[{"item_key": "b1_new", "source_order": 1, "title": "Board 1 New", "url": "http://b1.com", "meta": {}}],
        kept_items=[{"item_key": "b1_kept", "source_order": 2, "title": "Board 1 Kept", "url": "http://b1k.com", "meta": {}}],
    )

    board2 = create_board_bundle(
        "board2",
        new_items=[{"item_key": "b2_new", "source_order": 1, "title": "Board 2 New", "url": "http://b2.com", "meta": {}}],
        kept_items=[],
    )

    # Create research bundle
    research = create_research_bundle(
        "prog1",
        new_items=[
            {"item_key": "paper1", "published_at": "2024-01-20T00:00:00", "title": "Paper 1", "source_order": 1},
            {"item_key": "paper2", "published_at": "2024-01-15T00:00:00", "title": "Paper 2", "source_order": 2},
        ],
        kept_items=[
            {"item_key": "paper3", "published_at": "2024-01-10T00:00:00", "title": "Paper 3", "source_order": 3},
        ],
    )

    # Store as artifacts
    board1_id = artifact_repo.put(kind="board_bundle", schema_version="v1", content=board1, producer_engine="BoardRunEngine", producer_version="v1", job_id="test_job")
    board2_id = artifact_repo.put(kind="board_bundle", schema_version="v1", content=board2, producer_engine="BoardRunEngine", producer_version="v1", job_id="test_job")
    research_id = artifact_repo.put(kind="research_bundle", schema_version="v1", content=research, producer_engine="ResearchRunEngine", producer_version="v1", job_id="test_job")

    # Create compose job
    job = Job(
        job_id="compose_job",
        job_type="issue_compose",
        input_json=json.dumps({
            "follow_spec": {
                "follow_id": "follow1",
                "name": "E2E Test Follow",
                "description": "End-to-end test",
                "board_ids": ["board1", "board2"],
                "research_program_ids": ["prog1"],
            },
            "window": {"since": "2024-01-01", "until": "2024-01-31"},
            "research_bundle_id": research_id,
            "board_bundle_ids": [board1_id, board2_id],
        }),
    )
    job_repo.create_job(job)

    # Execute
    output_json = handler.execute(job, ctx)
    output = json.loads(output_json)

    # Verify artifact
    artifact = artifact_repo.get(output["artifact_id"])
    issue = artifact.content

    # Verify structure
    assert len(issue["sections"]) == 3  # 2 boards + 1 research
    assert issue["sections"][0]["section_id"] == "board.board1"
    assert issue["sections"][1]["section_id"] == "board.board2"
    assert issue["sections"][2]["section_id"] == "research.prog1"

    # Verify board1 items (new before kept)
    board1_items = issue["sections"][0]["items"]
    assert len(board1_items) == 2
    assert board1_items[0]["item_key"] == "b1_new"
    assert board1_items[1]["item_key"] == "b1_kept"

    # Verify board2 items
    board2_items = issue["sections"][1]["items"]
    assert len(board2_items) == 1
    assert board2_items[0]["item_key"] == "b2_new"

    # Verify research items (sorted by published_at DESC)
    research_items = issue["sections"][2]["items"]
    assert len(research_items) == 3
    assert research_items[0]["item_key"] == "paper1"  # 2024-01-20
    assert research_items[1]["item_key"] == "paper2"  # 2024-01-15
    assert research_items[2]["item_key"] == "paper3"  # 2024-01-10

    # Verify metadata
    assert issue["metadata"]["total_items"] == 6
    assert issue["metadata"]["section_count"] == 3
