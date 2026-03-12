"""Wait semantics tests — wait=true timeout returns 202 (not 408)."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.app.main import app


def test_sniffer_wait_timeout_returns_202():
    client = TestClient(app)
    resp = client.post(
        "/sniffer/search?wait=true&timeout=1",
        json={"keyword": f"test-{uuid.uuid4().hex[:8]}"},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data.get("job_id")
    assert data.get("status") in ("queued", "running")
    assert isinstance(data.get("results"), list)
    assert "summary" in data


def test_sources_wait_timeout_returns_202():
    client = TestClient(app)

    endpoint = f"https://example.com/rss/{uuid.uuid4().hex[:8]}"
    create = client.post("/sources", json={
        "source_type": "rss",
        "name": "Test Source",
        "endpoint": endpoint,
        "config": {},
        "enabled": True,
        "schedule_minutes": 30,
    })
    assert create.status_code == 200
    source_id = create.json()["source_id"]

    run = client.post(f"/sources/{source_id}/run?wait=true&timeout=1")
    assert run.status_code == 202
    data = run.json()
    assert data.get("job_id")
    assert data.get("status") in ("queued", "running")


def test_kg_relink_wait_timeout_returns_202():
    client = TestClient(app)
    resp = client.post("/knowledge-bases/kb_test/graph/nodes/node_test/relink?wait=true&timeout=1")
    assert resp.status_code == 202
    data = resp.json()
    assert data.get("job_id")
    assert data.get("status") in ("queued", "running")
