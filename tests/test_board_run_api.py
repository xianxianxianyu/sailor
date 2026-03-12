"""Tests for Board Run API endpoints"""
import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.board.repository import BoardRepository
from core.storage.db import Database


@pytest.fixture(scope="function", autouse=False)
def api_client(tmp_path):
    """Create test API client with test database"""
    # Create unique test database path for this test
    test_db_path = tmp_path / "data" / "sailor.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)

    # Save and set environment variable
    old_db_path = os.environ.get("SAILOR_DB_PATH")
    os.environ["SAILOR_DB_PATH"] = str(test_db_path)

    try:
        # Force reimport to get fresh modules
        import sys
        import importlib

        # Remove cached modules
        modules_to_reload = [m for m in sys.modules.keys() if m.startswith('backend.app')]
        for mod in modules_to_reload:
            del sys.modules[mod]

        # Import after clearing cache
        from backend.app.container import build_container
        from fastapi import FastAPI
        from backend.app.routers.boards import mount_board_routes
        from backend.app.routers.artifacts import mount_artifact_routes

        # Build container with test path
        container = build_container(tmp_path)

        # Verify database path
        assert str(container.db.db_path) == str(test_db_path), \
            f"Database path mismatch: {container.db.db_path} != {test_db_path}"

        # Create fresh app
        app = FastAPI(title="Sailor Test", version="0.1.0")

        # Mount routes with test container
        for board_router in mount_board_routes(container):
            app.include_router(board_router)
        app.include_router(mount_artifact_routes(container))

        client = TestClient(app)

        yield client, container
    finally:
        # Stop scheduler to avoid interference
        if hasattr(container, 'scheduler') and container.scheduler:
            try:
                container.scheduler.stop()
            except:
                pass

        # Restore environment
        if old_db_path is not None:
            os.environ["SAILOR_DB_PATH"] = old_db_path
        else:
            os.environ.pop("SAILOR_DB_PATH", None)


def test_trigger_board_run(api_client):
    """Test POST /boards/{board_id}/run"""
    client, container = api_client
    board_repo = container.board_repo

    # Create board and snapshots
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({"language": "python"}),
    )

    baseline_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(baseline_snapshot_id, [
        {
            "item_key": "v1:github_repo:owner1/repo1",
            "source_order": 1,
            "title": "Repo 1",
            "url": "https://github.com/owner1/repo1",
            "meta_json": json.dumps({"stars": 100}),
        }
    ])

    current_snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(current_snapshot_id, [
        {
            "item_key": "v1:github_repo:owner2/repo2",
            "source_order": 1,
            "title": "Repo 2",
            "url": "https://github.com/owner2/repo2",
            "meta_json": json.dumps({"stars": 200}),
        }
    ])

    # Trigger board run
    response = client.post(
        f"/boards/{board.board_id}/run",
        json={
            "snapshot_id": current_snapshot_id,
            "baseline_snapshot_id": baseline_snapshot_id,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    job_id = data["job_id"]

    # Simulate worker consuming the job
    container.job_runner.run(job_id)
    job = container.job_repo.get_job(job_id)
    assert job is not None
    assert job.status == "succeeded"

    output = json.loads(job.output_json or "{}")
    assert output.get("bundle_id") is not None
    assert output.get("artifact_id") is not None

    artifact_id = output["artifact_id"]
    artifact_resp = client.get(f"/artifacts/{artifact_id}")
    assert artifact_resp.status_code == 200
    artifact = artifact_resp.json()
    assert artifact["metadata"]["new_count"] == 1
    assert artifact["metadata"]["removed_count"] == 1
    assert artifact["metadata"]["kept_count"] == 0


def test_trigger_board_run_no_baseline(api_client):
    """Test board run without baseline (initial run)"""
    client, container = api_client
    board_repo = container.board_repo

    # Create board and snapshot
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({}),
    )

    snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(snapshot_id, [
        {
            "item_key": "v1:github_repo:owner1/repo1",
            "source_order": 1,
            "title": "Repo 1",
            "url": "https://github.com/owner1/repo1",
            "meta_json": json.dumps({"stars": 100}),
        }
    ])

    # Trigger board run without baseline
    response = client.post(
        f"/boards/{board.board_id}/run",
        json={"snapshot_id": snapshot_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    job_id = data["job_id"]

    container.job_runner.run(job_id)
    job = container.job_repo.get_job(job_id)
    assert job is not None
    assert job.status == "succeeded"

    output = json.loads(job.output_json or "{}")
    artifact_id = output["artifact_id"]
    artifact_resp = client.get(f"/artifacts/{artifact_id}")
    assert artifact_resp.status_code == 200
    artifact = artifact_resp.json()
    assert artifact["metadata"]["new_count"] == 1
    assert artifact["metadata"]["removed_count"] == 0
    assert artifact["metadata"]["kept_count"] == 0


def test_trigger_board_run_board_not_found(api_client):
    """Test error handling for non-existent board"""
    client, container = api_client

    response = client.post(
        "/boards/board_nonexistent/run",
        json={"snapshot_id": "snap_test"}
    )

    assert response.status_code == 404
    assert "Board not found" in response.json()["detail"]


def test_trigger_board_run_snapshot_not_found(api_client):
    """Test error handling for non-existent snapshot"""
    client, container = api_client
    board_repo = container.board_repo

    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({}),
    )

    response = client.post(
        f"/boards/{board.board_id}/run",
        json={"snapshot_id": "snap_nonexistent"}
    )

    assert response.status_code == 404
    assert "Snapshot not found" in response.json()["detail"]


def test_list_board_runs(api_client):
    """Test GET /boards/{board_id}/runs"""
    client, container = api_client
    board_repo = container.board_repo

    # Create board and run
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({}),
    )

    snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(snapshot_id, [
        {
            "item_key": "v1:github_repo:owner1/repo1",
            "source_order": 1,
            "title": "Repo 1",
            "url": "https://github.com/owner1/repo1",
            "meta_json": json.dumps({"stars": 100}),
        }
    ])

    # Trigger run (enqueue)
    run_resp = client.post(
        f"/boards/{board.board_id}/run",
        json={"snapshot_id": snapshot_id}
    )
    assert run_resp.status_code == 200
    job_id = run_resp.json()["job_id"]
    container.job_runner.run(job_id)

    # List runs
    response = client.get(f"/boards/{board.board_id}/runs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["bundle_id"] is not None
    assert data[0]["artifact_id"] is not None


def test_get_artifact(api_client):
    """Test GET /artifacts/{artifact_id}"""
    client, container = api_client
    board_repo = container.board_repo

    # Create board and run
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({}),
    )

    snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(snapshot_id, [
        {
            "item_key": "v1:github_repo:owner1/repo1",
            "source_order": 1,
            "title": "Repo 1",
            "url": "https://github.com/owner1/repo1",
            "meta_json": json.dumps({"stars": 100}),
        }
    ])

    # Trigger run
    run_response = client.post(
        f"/boards/{board.board_id}/run",
        json={"snapshot_id": snapshot_id}
    )
    assert run_response.status_code == 200, f"Failed: {run_response.text}"
    job_id = run_response.json()["job_id"]

    container.job_runner.run(job_id)
    job = container.job_repo.get_job(job_id)
    assert job is not None
    assert job.status == "succeeded"

    output = json.loads(job.output_json or "{}")
    artifact_id = output["artifact_id"]

    # Get artifact
    response = client.get(f"/artifacts/{artifact_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["artifact_id"] == artifact_id
    assert data["kind"] == "board_bundle"
    assert data["schema_version"] == "v1"
    assert "content" in data
    assert data["content"]["delta"] is not None


def test_list_artifacts(api_client):
    """Test GET /artifacts with filters"""
    client, container = api_client

    # List all artifacts
    response = client.get("/artifacts")
    assert response.status_code == 200

    # List by kind
    response = client.get("/artifacts?kind=board_bundle")
    assert response.status_code == 200

    # List with limit
    response = client.get("/artifacts?limit=10")
    assert response.status_code == 200


def test_get_latest_artifact(api_client):
    """Test GET /artifacts/latest/{kind}"""
    client, container = api_client
    board_repo = container.board_repo

    # Create board and run
    board = board_repo.upsert_board(
        provider="github",
        kind="repos",
        name="python",
        config_json=json.dumps({}),
    )

    snapshot_id = board_repo.create_snapshot(
        board_id=board.board_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )
    board_repo.add_snapshot_items(snapshot_id, [
        {
            "item_key": "v1:github_repo:owner1/repo1",
            "source_order": 1,
            "title": "Repo 1",
            "url": "https://github.com/owner1/repo1",
            "meta_json": json.dumps({"stars": 100}),
        }
    ])

    # Trigger run (enqueue)
    run_resp = client.post(
        f"/boards/{board.board_id}/run",
        json={"snapshot_id": snapshot_id}
    )
    assert run_resp.status_code == 200
    job_id = run_resp.json()["job_id"]
    container.job_runner.run(job_id)

    # Get latest
    response = client.get("/artifacts/latest/board_bundle")

    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "board_bundle"
