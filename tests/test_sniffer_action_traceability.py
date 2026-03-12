"""P1-3 contract tests: sniffer actions are traceable via job_id events."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import SniffResult


def _create_project_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "seed_entries.json").write_text("[]", encoding="utf-8")
    (tmp_path / "1.md").write_text("<opml/>", encoding="utf-8")


@pytest.fixture()
def api_client(tmp_path: Path):
    test_db_path = tmp_path / "data" / "sailor.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)

    old_db_path = os.environ.get("SAILOR_DB_PATH")
    os.environ["SAILOR_DB_PATH"] = str(test_db_path)

    container = None
    try:
        _create_project_files(tmp_path)

        for mod in [m for m in sys.modules.keys() if m.startswith("backend.app")]:
            del sys.modules[mod]

        from backend.app.container import build_container
        from backend.app.routers.jobs import mount_job_routes
        from backend.app.routers.sniffer import mount_sniffer_routes

        container = build_container(tmp_path)

        app = FastAPI(title="Sailor Test", version="0.1.0")
        app.include_router(mount_sniffer_routes(container))
        app.include_router(mount_job_routes(container))
        client = TestClient(app)

        yield client, container
    finally:
        if container is not None and getattr(container, "scheduler", None):
            try:
                container.scheduler.stop()
            except Exception:
                pass

        if old_db_path is not None:
            os.environ["SAILOR_DB_PATH"] = old_db_path
        else:
            os.environ.pop("SAILOR_DB_PATH", None)


def test_save_to_kb_and_convert_source_emit_events_with_job_id(api_client):
    client, container = api_client

    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb_{suffix}"
    container.kb_repo.create_kb(kb_id, name=f"KB {suffix}")

    result_id = f"sr_{suffix}"
    container.sniffer_repo.save_results([
        SniffResult(
            result_id=result_id,
            channel="hackernews",
            title="Test Result",
            url=f"https://example.com/{result_id}",
            snippet="Snippet",
            author="tester",
            published_at=None,
            media_type="article",
            metrics={},
            raw_data={},
            query_keyword="test",
            created_at=datetime.utcnow(),
        )
    ])

    # Save-to-KB is jobified (default wait=false => 202 + job_id).
    resp = client.post(f"/sniffer/results/{result_id}/save-to-kb", json={"kb_id": kb_id})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    assert job_id

    container.job_runner.run(job_id)

    events = client.get(f"/jobs/{job_id}/events").json()
    assert any(e.get("event_type") == "SavedToKB" for e in events)
    assert all(e.get("run_id") == job_id for e in events)

    # Convert-to-source is jobified (default wait=false => 202 + job_id).
    resp2 = client.post(f"/sniffer/results/{result_id}/convert-source", json={"name": "My Source"})
    assert resp2.status_code == 202
    job_id2 = resp2.json()["job_id"]
    assert job_id2

    container.job_runner.run(job_id2)

    events2 = client.get(f"/jobs/{job_id2}/events").json()
    assert any(e.get("event_type") == "ConvertedToSource" for e in events2)
    assert all(e.get("run_id") == job_id2 for e in events2)
