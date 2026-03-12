from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, container
from core.models import Job, Resource


def _patch_create_job_to_fail(monkeypatch: pytest.MonkeyPatch, job_types: set[str]) -> None:
    original = container.job_repo.create_job

    def create_job(job: Job) -> Job:
        created = original(job)
        if job.job_type in job_types:
            container.job_repo.update_status(
                job.job_id,
                "failed",
                error_class="test",
                error_message="forced failure",
            )
        return created

    monkeypatch.setattr(container.job_repo, "create_job", create_job)


def test_sniffer_compare_wait_failed_returns_200(monkeypatch: pytest.MonkeyPatch):
    _patch_create_job_to_fail(monkeypatch, {"sniffer_compare"})
    client = TestClient(app)

    resp = client.post("/sniffer/compare?wait=true&timeout=5", json={"result_ids": ["r1", "r2"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("job_id")
    assert data.get("status") == "failed"
    assert data.get("error_message")


def test_sources_run_wait_failed_returns_200(monkeypatch: pytest.MonkeyPatch):
    _patch_create_job_to_fail(monkeypatch, {"source_run"})
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

    resp = client.post(f"/sources/{source_id}/run?wait=true&timeout=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("job_id")
    assert data.get("status") == "failed"
    assert data.get("error_message")


def test_analyze_resource_wait_failed_returns_200(monkeypatch: pytest.MonkeyPatch):
    _patch_create_job_to_fail(monkeypatch, {"resource_analyze"})
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

    resp = client.post(f"/resources/{rid}/analyze?wait=true&timeout=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("job_id")
    assert data.get("status") == "failed"
    assert data.get("error_message")
