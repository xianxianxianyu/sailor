from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app, container
from core.models import Job
from core.runner.policy import TOOL_TO_JOB_TYPE


def test_confirm_approve_creates_execution_job_and_persists_it():
    client = TestClient(app)

    parent_job_id = uuid.uuid4().hex[:12]
    container.job_repo.create_job(Job(
        job_id=parent_job_id,
        job_type="test_confirm_parent",
        input_json="{}",
    ))

    pending = container.policy_gate.create_pending(
        action_type="propose_source",
        payload={
            "name": f"Confirm Source {parent_job_id}",
            "endpoint": f"https://example.com/{parent_job_id}.xml",
            "source_type": "rss",
            "schedule_minutes": 30,
        },
        job_id=parent_job_id,
    )

    listed = client.get(f"/confirms/{pending.confirm_id}")
    assert listed.status_code == 200
    listed_data = listed.json()
    assert listed_data["payload"]["job_type"] == "upsert_source"
    assert listed_data["payload"]["input_json"]["endpoint"].endswith(f"/{parent_job_id}.xml")
    assert listed_data["payload"]["display"]["name"] == f"Confirm Source {parent_job_id}"

    resp = client.post(f"/confirms/{pending.confirm_id}/resolve", json={"action": "approve"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["execution_job_id"]

    execution_job_id = data["execution_job_id"]
    job_resp = client.get(f"/jobs/{execution_job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["job_type"] == "upsert_source"

    refreshed = client.get(f"/confirms/{pending.confirm_id}")
    assert refreshed.status_code == 200
    assert refreshed.json()["execution_job_id"] == execution_job_id

    executed = container.job_runner.run(execution_job_id)
    assert executed.status == "succeeded"
    output = json.loads(executed.output_json or "{}")
    source = container.source_repo.get_source(output["source_id"])
    assert source is not None
    assert source.name == f"Confirm Source {parent_job_id}"


def test_confirm_reject_does_not_create_execution_job():
    client = TestClient(app)

    parent_job_id = uuid.uuid4().hex[:12]
    container.job_repo.create_job(Job(
        job_id=parent_job_id,
        job_type="test_confirm_parent",
        input_json="{}",
    ))

    pending = container.policy_gate.create_pending(
        action_type="delete_source",
        payload={"source_id": f"src_{parent_job_id}"},
        job_id=parent_job_id,
    )

    resp = client.post(f"/confirms/{pending.confirm_id}/resolve", json={"action": "reject"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["execution_job_id"] is None


def test_all_confirm_job_types_have_registered_handlers():
    handlers = container.job_runner._handlers
    missing = sorted({job_type for job_type in TOOL_TO_JOB_TYPE.values() if job_type not in handlers})
    assert missing == []
