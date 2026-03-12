"""Jobs API tests — /jobs/{job_id} and /jobs/{job_id}/events."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.app.main import app, container
from core.models import Job


def test_get_job_and_events_reachable():
    client = TestClient(app)

    job_id = uuid.uuid4().hex[:12]
    container.job_repo.create_job(Job(
        job_id=job_id,
        job_type="test",
        input_json="{}",
    ))

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["job_type"] == "test"
    assert data["status"] == "queued"

    ev = client.get(f"/jobs/{job_id}/events")
    assert ev.status_code == 200
    assert isinstance(ev.json(), list)


def test_get_job_404():
    client = TestClient(app)
    resp = client.get("/jobs/job_does_not_exist_123")
    assert resp.status_code == 404



def test_cancel_queued_job():
    client = TestClient(app)

    job_id = uuid.uuid4().hex[:12]
    container.job_repo.create_job(Job(
        job_id=job_id,
        job_type="test",
        input_json="{}",
    ))

    resp = client.post(f"/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"job_id": job_id, "status": "cancelled", "cancel_requested": True}

    stored = container.job_repo.get_job(job_id)
    assert stored is not None
    assert stored.status == "cancelled"


def test_cancel_running_job_sets_cancel_requested():
    client = TestClient(app)

    job_id = uuid.uuid4().hex[:12]
    container.job_repo.create_job(Job(
        job_id=job_id,
        job_type="test",
        input_json="{}",
    ))
    container.job_repo.update_status(job_id, "running")

    resp = client.post(f"/jobs/{job_id}/cancel")
    assert resp.status_code == 202
    data = resp.json()
    assert data == {"job_id": job_id, "status": "running", "cancel_requested": True}

    stored = container.job_repo.get_job(job_id)
    assert stored is not None
    assert stored.status == "running"
    assert stored.metadata.get("cancel_requested") is True


def test_cancel_finished_job_returns_409():
    client = TestClient(app)

    job_id = uuid.uuid4().hex[:12]
    container.job_repo.create_job(Job(
        job_id=job_id,
        job_type="test",
        input_json="{}",
    ))
    container.job_repo.update_status(job_id, "succeeded", output_json="{}")

    resp = client.post(f"/jobs/{job_id}/cancel")
    assert resp.status_code == 409
