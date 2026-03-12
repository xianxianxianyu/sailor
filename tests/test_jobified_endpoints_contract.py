"""P0 contract tests — heavy endpoints enqueue by default (wait=false)."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.app.main import app, container
from core.models import Resource


def test_analyze_resource_enqueues_by_default():
    client = TestClient(app)

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    container.resource_repo.upsert(Resource(
        resource_id=rid,
        canonical_url=f"https://example.com/{rid}",
        source="test",
        provenance={},
        title="Test Article",
        published_at=None,
        text="This is long enough for analysis. " * 5,
        original_url=f"https://example.com/{rid}",
        topics=["General"],
        summary="Test summary",
    ))

    resp = client.post(f"/resources/{rid}/analyze")
    assert resp.status_code == 202
    data = resp.json()
    assert data.get("job_id")
    assert data.get("status") in ("queued", "running")


def test_kb_reports_generate_enqueues_by_default():
    client = TestClient(app)
    resp = client.post("/knowledge-bases/kb_test/reports", json={"report_types": ["summary"]})
    assert resp.status_code == 202
    data = resp.json()
    assert data.get("job_id")
    assert data.get("status") in ("queued", "running")

