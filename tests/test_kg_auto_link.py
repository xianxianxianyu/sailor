"""
Test P1 auto-linking functionality.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from core.agent.base import LLMClient, LLMConfig
from core.kg import KGLinkEngine, KGAddNodeHandler
from core.runner.handlers import RunContext
from core.storage import Database, KBGraphRepository, JobRepository, KnowledgeBaseRepository, ResourceRepository
from core.models import Job, Resource


@pytest.fixture
def test_db(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    return db


@pytest.fixture
def repos(test_db):
    return {
        "kb_graph": KBGraphRepository(test_db),
        "kb": KnowledgeBaseRepository(test_db),
        "resource": ResourceRepository(test_db),
        "job": JobRepository(test_db),
    }


def test_kg_link_engine_basic(repos):
    """Test that KGLinkEngine can be instantiated."""
    config = LLMConfig(api_key="test", model="gpt-4o-mini")
    llm = LLMClient(config)
    engine = KGLinkEngine(llm)

    assert engine is not None
    assert engine.llm is not None


def test_kg_add_node_handler_no_candidates(repos):
    """Test handler when there are no candidates."""
    config = LLMConfig(api_key="test", model="gpt-4o-mini")
    llm = LLMClient(config)
    engine = KGLinkEngine(llm)
    handler = KGAddNodeHandler(repos["kb_graph"], engine)

    # Create KB and resource
    kb = repos["kb"].create_kb("kb_test", "Test KB")
    resource = Resource(
        resource_id=f"res_{uuid.uuid4().hex[:8]}",
        canonical_url="https://example.com/1",
        source="test",
        provenance={"source": "test"},
        title="Test Resource",
        published_at=None,
        text="Test content",
        original_url="https://example.com/1",
        topics=["test"],
        summary="Test summary",
    )
    repos["resource"].upsert(resource)
    repos["kb"].add_item(kb.kb_id, resource.resource_id)

    # Create job
    job = Job(
        job_id="test_job",
        job_type="kg_add_node",
        status="queued",
        input_json=json.dumps({"kb_id": kb.kb_id, "node_id": resource.resource_id}),
        metadata={},
    )

    # Create context
    ctx = RunContext(job_repo=repos["job"], run_id=job.job_id)

    # Execute - should succeed with 0 edges (no candidates)
    result = handler.execute(job, ctx)
    assert result == '{"edges_created": 0}'


def test_repository_methods(repos):
    """Test new repository methods."""
    kb = repos["kb"].create_kb("kb_test2", "Test KB 2")

    # Create some resources
    for i in range(3):
        resource = Resource(
            resource_id=f"res_{uuid.uuid4().hex[:8]}",
            canonical_url=f"https://example.com/{i}",
            source="test",
            provenance={"source": "test"},
            title=f"Resource {i}",
            published_at=None,
            text=f"Content {i}",
            original_url=f"https://example.com/{i}",
            topics=["test"],
            summary=f"Summary {i}",
        )
        repos["resource"].upsert(resource)
        repos["kb"].add_item(kb.kb_id, resource.resource_id)

    # Test list_recent_nodes
    nodes = repos["kb_graph"].list_recent_nodes(kb.kb_id, limit=2)
    assert len(nodes) == 2

    # Test get_deleted_pairs (should be empty)
    deleted = repos["kb_graph"].get_deleted_pairs(kb.kb_id)
    assert len(deleted) == 0

    # Create and delete an edge
    nodes_all = repos["kb_graph"].list_nodes(kb.kb_id)
    if len(nodes_all) >= 2:
        repos["kb_graph"].upsert_edge(
            kb.kb_id,
            nodes_all[0]["id"],
            nodes_all[1]["id"],
            "test reason",
            created_run_id="test_run",
        )
        repos["kb_graph"].soft_delete_edge(
            kb.kb_id,
            nodes_all[0]["id"],
            nodes_all[1]["id"],
            deleted_by="user",
            deleted_run_id="test_delete_run",
        )

        # Now should have one deleted pair
        deleted = repos["kb_graph"].get_deleted_pairs(kb.kb_id)
        assert len(deleted) == 1


def test_schema_migration(test_db):
    """Test that deleted_run_id column exists."""
    with test_db.connect() as conn:
        rows = conn.execute("PRAGMA table_info(kb_graph_edges)").fetchall()
        columns = {row["name"] for row in rows}
        assert "deleted_run_id" in columns
        assert "created_run_id" in columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
