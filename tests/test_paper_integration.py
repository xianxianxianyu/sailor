"""Paper Engine Integration Tests

测试 API endpoints 和端到端同步流程
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, container


@pytest.fixture
def client() -> TestClient:
    """创建 test client"""
    return TestClient(app)


# ========== API Endpoints Tests ==========


def test_healthz_reachable(client: TestClient):
    """测试 healthz endpoint"""
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_list_paper_sources_reachable(client: TestClient):
    """测试 GET /paper-sources"""
    resp = client.get("/paper-sources")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_paper_source(client: TestClient):
    """测试 POST /paper-sources"""
    data = {
        "platform": "arxiv",
        "endpoint": "cat:cs.AI",
        "name": "arXiv AI Papers",
        "config": {"max_results": 50},
        "enabled": True,
    }

    resp = client.post("/paper-sources", json=data)
    assert resp.status_code == 200

    result = resp.json()
    assert result["platform"] == "arxiv"
    assert result["endpoint"] == "cat:cs.AI"
    assert result["source_id"].startswith("paper_arxiv_")


def test_get_paper_source(client: TestClient):
    """测试 GET /paper-sources/{id}"""
    # 先创建
    create_resp = client.post(
        "/paper-sources",
        json={
            "platform": "arxiv",
            "endpoint": "cat:cs.LG",
            "name": "Test Source",
            "config": {},
        },
    )
    source_id = create_resp.json()["source_id"]

    # 再获取
    resp = client.get(f"/paper-sources/{source_id}")
    assert resp.status_code == 200
    assert resp.json()["source_id"] == source_id


def test_update_paper_source(client: TestClient):
    """测试 PATCH /paper-sources/{id}"""
    # 创建
    create_resp = client.post(
        "/paper-sources",
        json={
            "platform": "arxiv",
            "endpoint": "cat:cs.CV",
            "name": "Original Name",
            "config": {},
        },
    )
    source_id = create_resp.json()["source_id"]

    # 更新
    update_resp = client.patch(
        f"/paper-sources/{source_id}",
        json={"name": "Updated Name", "enabled": False},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Name"
    assert update_resp.json()["enabled"] is False


def test_delete_paper_source(client: TestClient):
    """测试 DELETE /paper-sources/{id}"""
    # 创建
    create_resp = client.post(
        "/paper-sources",
        json={
            "platform": "arxiv",
            "endpoint": "cat:cs.RO",
            "name": "To Delete",
            "config": {},
        },
    )
    source_id = create_resp.json()["source_id"]

    # 删除
    delete_resp = client.delete(f"/paper-sources/{source_id}")
    assert delete_resp.status_code == 200

    # 验证已删除
    get_resp = client.get(f"/paper-sources/{source_id}")
    assert get_resp.status_code == 404


def test_list_papers_reachable(client: TestClient):
    """测试 GET /papers"""
    resp = client.get("/papers")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_papers_by_source_reachable(client: TestClient):
    """测试 GET /paper-sources/{id}/papers"""
    # 创建 source
    create_resp = client.post(
        "/paper-sources",
        json={
            "platform": "arxiv",
            "endpoint": "cat:cs.NE",
            "name": "Test",
            "config": {},
        },
    )
    source_id = create_resp.json()["source_id"]

    # 查询 papers
    resp = client.get(f"/paper-sources/{source_id}/papers")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_runs_reachable(client: TestClient):
    """测试 GET /paper-sources/{id}/runs"""
    # 创建 source
    create_resp = client.post(
        "/paper-sources",
        json={
            "platform": "arxiv",
            "endpoint": "cat:cs.CL",
            "name": "Test",
            "config": {},
        },
    )
    source_id = create_resp.json()["source_id"]

    # 查询 runs
    resp = client.get(f"/paper-sources/{source_id}/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ========== End-to-End Sync Tests ==========


@patch("core.paper.tools.urlopen")
def test_run_paper_source_with_mock(mock_urlopen, client: TestClient):
    """测试 paper source run：enqueue -> worker(run) -> 入库 + provenance"""
    # Mock arXiv API 响应
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/2401.12345</id>
            <title>Test Paper Title</title>
            <summary>Test abstract</summary>
            <published>2024-01-15T00:00:00Z</published>
            <author><name>Alice</name></author>
            <author><name>Bob</name></author>
            <link title="pdf" href="https://arxiv.org/pdf/2401.12345.pdf"/>
        </entry>
    </feed>
    """

    mock_response = MagicMock()
    mock_response.read.return_value = mock_xml.encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    # 创建 source
    create_resp = client.post(
        "/paper-sources",
        json={
            "platform": "arxiv",
            "endpoint": "cat:cs.AI",
            "name": "Test arXiv",
            "config": {"max_results": 10},
        },
    )
    source_id = create_resp.json()["source_id"]

    # 触发同步
    run_resp = client.post(f"/paper-sources/{source_id}/run")
    assert run_resp.status_code == 200

    result = run_resp.json()
    assert result["source_id"] == source_id
    assert result["status"] == "queued"
    job_id = result["job_id"]

    # 模拟 worker：消费 job 并执行
    container.job_runner.run(job_id)

    # 验证 job 已完成
    job_resp = client.get(f"/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "succeeded"

    # 验证 papers 已插入
    papers_resp = client.get(f"/paper-sources/{source_id}/papers")
    papers = papers_resp.json()
    assert len(papers) == 1
    assert papers[0]["title"] == "Test Paper Title"
    assert papers[0]["canonical_id"] == "arxiv:2401.12345"

    # 验证 tool_calls/raw_captures 可按 job_id 追溯
    with container.db.connect() as conn:
        tc_row = conn.execute(
            """
            SELECT tool_call_id, status, output_ref
            FROM tool_calls
            WHERE run_id = ? AND tool_name = ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (job_id, "paper.fetch_arxiv_atom"),
        ).fetchone()
        assert tc_row is not None
        assert tc_row["status"] == "succeeded"
        assert tc_row["output_ref"]

        rc_row = conn.execute(
            """
            SELECT capture_id, content_type
            FROM raw_captures
            WHERE capture_id = ? AND tool_call_id = ?
            LIMIT 1
            """,
            (tc_row["output_ref"], tc_row["tool_call_id"]),
        ).fetchone()
        assert rc_row is not None
        assert rc_row["content_type"] == "xml"


def test_run_disabled_source_fails(client: TestClient):
    """测试运行 disabled source 应该失败"""
    # 创建 disabled source
    create_resp = client.post(
        "/paper-sources",
        json={
            "platform": "arxiv",
            "endpoint": "cat:cs.AI",
            "name": "Disabled Source",
            "config": {},
            "enabled": False,
        },
    )
    source_id = create_resp.json()["source_id"]

    # 尝试运行
    run_resp = client.post(f"/paper-sources/{source_id}/run")
    assert run_resp.status_code == 400
    assert "disabled" in run_resp.json()["detail"].lower()


def test_run_nonexistent_source_fails(client: TestClient):
    """测试运行不存在的 source 应该失败"""
    resp = client.post("/paper-sources/paper_nonexistent_123/run")
    assert resp.status_code == 404


# ========== Platform Dispatcher Tests ==========


def test_unsupported_platform_fails(client: TestClient):
    """测试不支持的 platform 应该失败"""
    # 创建 unsupported platform source
    create_resp = client.post(
        "/paper-sources",
        json={
            "platform": "unsupported_platform",
            "endpoint": "test",
            "name": "Unsupported",
            "config": {},
        },
    )
    source_id = create_resp.json()["source_id"]

    # 尝试运行：job 创建应成功，执行由 worker 决定（这里用 job_runner.run 模拟）
    run_resp = client.post(f"/paper-sources/{source_id}/run")
    assert run_resp.status_code == 200
    job_id = run_resp.json()["job_id"]

    container.job_runner.run(job_id)
    job_resp = client.get(f"/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "failed"
