from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app, container
from core.models import Job, SniffResult


def test_sniffer_jobs_endpoint_returns_202_for_queued_job():
    client = TestClient(app)

    job_id = f"sniffer_job_{uuid.uuid4().hex[:12]}"
    container.job_repo.create_job(Job(
        job_id=job_id,
        job_type="sniffer_search",
        input_json=json.dumps({"keyword": "test"}),
    ))

    resp = client.get(f"/sniffer/jobs/{job_id}")
    assert resp.status_code == 202
    assert resp.headers.get("Location") == f"/jobs/{job_id}"

    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"
    assert isinstance(data["results"], list)


def test_sniffer_jobs_endpoint_returns_results_for_succeeded_job():
    client = TestClient(app)

    keyword = f"kw_{uuid.uuid4().hex[:8]}"
    r1 = SniffResult(
        result_id=f"res_{uuid.uuid4().hex[:12]}",
        channel="github",
        title="Test 1",
        url=f"https://example.com/{uuid.uuid4().hex[:8]}",
        snippet="hello",
        query_keyword=keyword,
    )
    r2 = SniffResult(
        result_id=f"res_{uuid.uuid4().hex[:12]}",
        channel="hackernews",
        title="Test 2",
        url=f"https://example.com/{uuid.uuid4().hex[:8]}",
        snippet="world",
        query_keyword=keyword,
    )
    container.sniffer_repo.save_results([r1, r2])

    job_id = f"sniffer_job_{uuid.uuid4().hex[:12]}"
    container.job_repo.create_job(Job(
        job_id=job_id,
        job_type="sniffer_search",
        input_json=json.dumps({"keyword": keyword}),
    ))
    container.job_repo.update_status(
        job_id,
        "succeeded",
        output_json=json.dumps({
            "result_ids": [r1.result_id, r2.result_id],
            "summary": {
                "total": 2,
                "keyword": keyword,
                "channel_distribution": {"github": 1, "hackernews": 1},
                "keyword_clusters": [],
                "time_distribution": {"unknown": 2},
                "top_by_engagement": [],
            },
        }),
    )

    resp = client.get(f"/sniffer/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "succeeded"
    assert len(data["results"]) == 2
    assert data["summary"]["total"] == 2
    assert data["summary"]["keyword"] == keyword


def test_sniffer_jobs_endpoint_returns_terminal_status_for_cancelled_job():
    client = TestClient(app)

    job_id = f"sniffer_job_{uuid.uuid4().hex[:12]}"
    container.job_repo.create_job(Job(
        job_id=job_id,
        job_type="sniffer_search",
        input_json=json.dumps({"keyword": "cancel"}),
    ))
    container.job_repo.update_status(job_id, "cancelled")

    resp = client.get(f"/sniffer/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "cancelled"
    assert data["results"] == []
