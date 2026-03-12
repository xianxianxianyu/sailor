"""Tests for BoardSnapshotHandler

Tests for board snapshot job handler and API integration.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from core.board import BoardRepository, BoardSnapshotHandler
from core.models import Job
from core.runner.handlers import RunContext
from core.storage.db import Database
from core.storage.job_repository import JobRepository


# ========== Fixtures ==========


@pytest.fixture
def handler_setup(tmp_path: Path):
    """Create handler with dependencies"""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    job_repo = JobRepository(db)
    board_repo = BoardRepository(db)

    handler = BoardSnapshotHandler(board_repo)

    # Create test job
    job = Job(job_id="test_job", job_type="board_snapshot")
    job_repo.create_job(job)

    ctx = RunContext(job_repo=job_repo, run_id="test_job", data_dir=tmp_path)

    return handler, ctx, board_repo, job_repo


# ========== Handler Tests ==========


def test_board_snapshot_handler_github(handler_setup):
    """Test handler execution with GitHub board"""
    handler, ctx, board_repo, job_repo = handler_setup

    # Create GitHub board
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="Python Trending",
        config_json=json.dumps({"language": "python"}),
    )

    # Create job
    job = Job(
        job_id="test_job",
        job_type="board_snapshot",
        input_json=json.dumps({"board_id": board.board_id}),
    )

    # Mock capture and ingest functions
    with patch("core.board.handlers.boards_capture_github") as mock_capture, \
         patch("core.board.handlers.boards_snapshot_ingest") as mock_ingest:

        mock_capture.return_value = "cap_test123"
        mock_ingest.return_value = "snap_test456"

        # Execute handler
        output_json = handler.execute(job, ctx)

        # Verify output
        output = json.loads(output_json)
        assert output["snapshot_id"] == "snap_test456"

        # Verify capture was called correctly
        mock_capture.assert_called_once()
        call_args = mock_capture.call_args
        assert call_args[0][0] == ctx
        assert call_args[0][1] == board.board_id
        assert call_args[0][2] == "python"  # language
        assert call_args[0][3] == "daily"  # since (default)

        # Verify ingest was called correctly
        mock_ingest.assert_called_once()
        ingest_args = mock_ingest.call_args
        assert ingest_args[1]["ctx"] == ctx
        assert ingest_args[1]["board_repo"] == handler.board_repo
        assert ingest_args[1]["board_id"] == board.board_id
        assert ingest_args[1]["raw_capture_ref"] == "cap_test123"

    # Verify events were emitted
    events = job_repo.list_events(run_id="test_job")
    event_types = [e.event_type for e in events]
    assert "BoardSnapshotStarted" in event_types
    assert "BoardSnapshotFinished" in event_types


def test_board_snapshot_handler_huggingface(handler_setup):
    """Test handler execution with HuggingFace board"""
    handler, ctx, board_repo, job_repo = handler_setup

    # Create HuggingFace board
    board = board_repo.upsert_board(
        provider="huggingface",
        kind="models",
        name="Top Models",
        config_json=json.dumps({"kind": "models", "limit": 50}),
    )

    # Create job
    job = Job(
        job_id="test_job",
        job_type="board_snapshot",
        input_json=json.dumps({"board_id": board.board_id}),
    )

    # Mock capture and ingest functions
    with patch("core.board.handlers.boards_capture_huggingface") as mock_capture, \
         patch("core.board.handlers.boards_snapshot_ingest") as mock_ingest:

        mock_capture.return_value = "cap_hf123"
        mock_ingest.return_value = "snap_hf456"

        # Execute handler
        output_json = handler.execute(job, ctx)

        # Verify output
        output = json.loads(output_json)
        assert output["snapshot_id"] == "snap_hf456"

        # Verify capture was called correctly
        mock_capture.assert_called_once()
        call_args = mock_capture.call_args
        assert call_args[0][0] == ctx
        assert call_args[0][1] == board.board_id
        assert call_args[0][2] == "models"  # kind
        assert call_args[0][3] == 50  # limit

        # Verify ingest was called
        mock_ingest.assert_called_once()


def test_board_snapshot_handler_unsupported_provider(handler_setup):
    """Test handler with unsupported provider"""
    handler, ctx, board_repo, job_repo = handler_setup

    # Create board with unsupported provider
    board = board_repo.upsert_board(
        provider="unsupported",
        kind="test",
        name="Test Board",
        config_json=json.dumps({}),
    )

    # Create job
    job = Job(
        job_id="test_job",
        job_type="board_snapshot",
        input_json=json.dumps({"board_id": board.board_id}),
    )

    # Execute handler - should raise ValueError
    with pytest.raises(ValueError, match="Unsupported provider"):
        handler.execute(job, ctx)


def test_board_snapshot_handler_board_not_found(handler_setup):
    """Test handler with non-existent board"""
    handler, ctx, board_repo, job_repo = handler_setup

    # Create job with non-existent board_id
    job = Job(
        job_id="test_job",
        job_type="board_snapshot",
        input_json=json.dumps({"board_id": "nonexistent"}),
    )

    # Execute handler - should raise ValueError
    with pytest.raises(ValueError, match="Board not found"):
        handler.execute(job, ctx)


# ========== API Integration Tests ==========


@pytest.fixture(scope="function", autouse=False)
def api_client(tmp_path: Path):
    """Create test API client with isolated test database"""
    import os

    # Create unique test database path for this test
    test_db_path = tmp_path / "data" / "sailor.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)

    old_db_path = os.environ.get("SAILOR_DB_PATH")
    os.environ["SAILOR_DB_PATH"] = str(test_db_path)

    container = None
    try:
        # Force reimport so settings/env are re-read
        import sys

        modules_to_reload = [m for m in sys.modules.keys() if m.startswith("backend.app")]
        for mod in modules_to_reload:
            del sys.modules[mod]

        from backend.app.container import build_container
        from fastapi import FastAPI
        from backend.app.routers.boards import mount_board_routes

        container = build_container(tmp_path)

        app = FastAPI(title="Sailor Test", version="0.1.0")
        for board_router in mount_board_routes(container):
            app.include_router(board_router)

        client = TestClient(app)
        yield client, container
    finally:
        # Stop scheduler to avoid interference
        if container is not None and getattr(container, "scheduler", None):
            try:
                container.scheduler.stop()
            except Exception:
                pass

        if old_db_path is not None:
            os.environ["SAILOR_DB_PATH"] = old_db_path
        else:
            os.environ.pop("SAILOR_DB_PATH", None)


def test_board_snapshot_api_endpoint(api_client):
    """Test API endpoint for triggering board snapshot"""
    client, container = api_client

    # Create a board
    board_data = {
        "provider": "github",
        "kind": "repos",
        "name": "Python Trending",
        "config": {"language": "python"},
    }
    response = client.post("/boards", json=board_data)
    assert response.status_code == 200
    board = response.json()
    board_id = board["board_id"]

    # Mock HTTP calls in capture functions
    mock_html = """
    <html>
        <article class="Box-row">
            <h2><a href="/test/repo">test/repo</a></h2>
            <p>Test description</p>
            <span class="d-inline-block float-sm-right">
                <svg><use xlink:href="#star"></use></svg>
                1,234
            </span>
            <span>TypeScript</span>
            <span class="d-inline-block float-sm-right">
                <svg><use xlink:href="#repo-forked"></use></svg>
                567
            </span>
            <span class="float-sm-right">
                <svg><use xlink:href="#star"></use></svg>
                89 stars today
            </span>
        </article>
    </html>
    """

    with patch("core.board.tools.urlopen") as mock_urlopen:
        mock_response = Mock()
        mock_response.read.return_value = mock_html.encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Trigger snapshot
        response = client.post(f"/boards/{board_id}/snapshot")
        assert response.status_code == 200

        result = response.json()
        assert "job_id" in result
        assert "snapshot_id" in result
        assert result["status"] == "queued"
        job_id = result["job_id"]

        # Simulate worker consuming the job
        container.job_runner.run(job_id)

        job = container.job_repo.get_job(job_id)
        assert job is not None
        assert job.status == "succeeded"

        output = json.loads(job.output_json or "{}")
        assert output.get("snapshot_id") is not None
        snapshot_id = output["snapshot_id"]

    # Verify snapshot was created
    response = client.get(f"/boards/{board_id}/snapshots/latest")
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["snapshot_id"] == snapshot_id


def test_board_snapshot_api_idempotency(api_client):
    """Test idempotency of snapshot endpoint"""
    client, container = api_client
    # Create a board
    board_data = {
        "provider": "github",
        "kind": "repos",
        "name": "Python Trending",
        "config": {"language": "python"},
    }
    response = client.post("/boards", json=board_data)
    board_id = response.json()["board_id"]

    # Mock HTTP calls
    mock_html = """
    <html>
        <article class="Box-row">
            <h2><a href="/test/repo">test/repo</a></h2>
        </article>
    </html>
    """

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = Mock()
        mock_response.read.return_value = mock_html.encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # First call
        response1 = client.post(f"/boards/{board_id}/snapshot")
        assert response1.status_code == 200
        result1 = response1.json()
        job_id1 = result1["job_id"]

        # Second call with same parameters
        response2 = client.post(f"/boards/{board_id}/snapshot")
        assert response2.status_code == 200
        result2 = response2.json()
        job_id2 = result2["job_id"]

        # Should return same job_id (idempotent)
        assert job_id1 == job_id2
