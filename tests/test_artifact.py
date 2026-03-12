"""Artifact Repository Unit Tests

Tests for ArtifactRepository CRUD operations and filtering.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.artifact import Artifact, ArtifactRepository
from core.storage.db import Database


@pytest.fixture
def artifact_repo(tmp_path: Path) -> ArtifactRepository:
    """Create temporary ArtifactRepository"""
    db_path = tmp_path / "test_artifact.db"
    db = Database(db_path)
    db.init_schema()  # Initialize jobs table
    return ArtifactRepository(db)


@pytest.fixture
def sample_job_id(artifact_repo: ArtifactRepository) -> str:
    """Create a sample job for testing"""
    # Insert a test job into the jobs table
    with artifact_repo.db.connect() as conn:
        job_id = "job_test_123"
        conn.execute(
            """
            INSERT INTO jobs (job_id, job_type, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, "test_job", "completed", datetime.utcnow().isoformat()),
        )
    return job_id


def test_artifact_put_and_get(artifact_repo: ArtifactRepository, sample_job_id: str):
    """Test basic artifact storage and retrieval"""
    # Store artifact
    artifact_id = artifact_repo.put(
        kind="research_bundle",
        schema_version="v1",
        content={"papers": [{"title": "Test Paper"}], "query": "AI research"},
        producer_engine="ResearchRunEngine",
        producer_version="v1.0",
        job_id=sample_job_id,
    )

    assert artifact_id.startswith("art_")

    # Retrieve artifact
    artifact = artifact_repo.get(artifact_id)
    assert artifact is not None
    assert artifact.artifact_id == artifact_id
    assert artifact.kind == "research_bundle"
    assert artifact.schema_version == "v1"
    assert artifact.content["query"] == "AI research"
    assert artifact.producer["engine"] == "ResearchRunEngine"
    assert artifact.producer["engine_version"] == "v1.0"
    assert artifact.job_id == sample_job_id
    assert artifact.created_at is not None


def test_artifact_list_with_filters(artifact_repo: ArtifactRepository, sample_job_id: str):
    """Test artifact listing with various filters"""
    # Create multiple artifacts
    now = datetime.utcnow()

    # Research bundle
    artifact_repo.put(
        kind="research_bundle",
        schema_version="v1",
        content={"papers": []},
        producer_engine="ResearchRunEngine",
        producer_version="v1.0",
        job_id=sample_job_id,
    )

    # Issue snapshot
    artifact_repo.put(
        kind="issue_snapshot",
        schema_version="v1",
        content={"issue_id": "123"},
        producer_engine="IssueComposerEngine",
        producer_version="v1.0",
        job_id=sample_job_id,
    )

    # Another research bundle
    artifact_repo.put(
        kind="research_bundle",
        schema_version="v1",
        content={"papers": []},
        producer_engine="ResearchRunEngine",
        producer_version="v1.0",
        job_id=sample_job_id,
    )

    # Test: List all artifacts
    all_artifacts = artifact_repo.list()
    assert len(all_artifacts) == 3

    # Test: Filter by kind
    research_artifacts = artifact_repo.list(kind="research_bundle")
    assert len(research_artifacts) == 2
    assert all(a.kind == "research_bundle" for a in research_artifacts)

    issue_artifacts = artifact_repo.list(kind="issue_snapshot")
    assert len(issue_artifacts) == 1
    assert issue_artifacts[0].kind == "issue_snapshot"

    # Test: Filter by job_id
    job_artifacts = artifact_repo.list(job_id=sample_job_id)
    assert len(job_artifacts) == 3


def test_artifact_find_latest_by_kind(artifact_repo: ArtifactRepository, sample_job_id: str):
    """Test finding latest artifact by kind"""
    # Create multiple research bundles with slight time differences
    for i in range(3):
        artifact_repo.put(
            kind="research_bundle",
            schema_version="v1",
            content={"iteration": i},
            producer_engine="ResearchRunEngine",
            producer_version="v1.0",
            job_id=sample_job_id,
        )

    # Find latest
    latest = artifact_repo.find_latest_by_kind("research_bundle")
    assert latest is not None
    assert latest.kind == "research_bundle"
    assert latest.content["iteration"] == 2  # Last one created

    # Test non-existent kind
    nonexistent = artifact_repo.find_latest_by_kind("nonexistent_kind")
    assert nonexistent is None


def test_artifact_with_large_content(artifact_repo: ArtifactRepository, sample_job_id: str):
    """Test artifact with content_ref for large content"""
    # Store artifact with content_ref
    artifact_id = artifact_repo.put(
        kind="board_bundle",
        schema_version="v1",
        content={"summary": "Large board data"},
        content_ref="file://data/artifacts/board_bundle_123.json",
        producer_engine="BoardRunEngine",
        producer_version="v1.0",
        job_id=sample_job_id,
    )

    # Retrieve and verify
    artifact = artifact_repo.get(artifact_id)
    assert artifact is not None
    assert artifact.content_ref == "file://data/artifacts/board_bundle_123.json"
    assert artifact.content["summary"] == "Large board data"


def test_artifact_input_refs(artifact_repo: ArtifactRepository, sample_job_id: str):
    """Test artifact with input_refs structure"""
    # Store artifact with input references
    input_refs = {
        "snapshot_ids": ["snap_001", "snap_002"],
        "bundle_ids": ["bundle_abc"],
        "job_ids": ["job_parent_123"],
    }

    artifact_id = artifact_repo.put(
        kind="board_bundle",
        schema_version="v1",
        content={"boards": []},
        producer_engine="BoardRunEngine",
        producer_version="v1.0",
        job_id=sample_job_id,
        input_refs=input_refs,
    )

    # Retrieve and verify
    artifact = artifact_repo.get(artifact_id)
    assert artifact is not None
    assert artifact.input_refs is not None
    assert artifact.input_refs["snapshot_ids"] == ["snap_001", "snap_002"]
    assert artifact.input_refs["bundle_ids"] == ["bundle_abc"]
    assert artifact.input_refs["job_ids"] == ["job_parent_123"]


def test_artifact_list_time_filters(artifact_repo: ArtifactRepository, sample_job_id: str):
    """Test artifact listing with time range filters"""
    now = datetime.utcnow()

    # Create artifacts (they'll have timestamps close to 'now')
    artifact_repo.put(
        kind="research_bundle",
        schema_version="v1",
        content={"test": 1},
        producer_engine="ResearchRunEngine",
        producer_version="v1.0",
        job_id=sample_job_id,
    )

    # Test: since filter (should include the artifact)
    since_past = now - timedelta(hours=1)
    artifacts_since = artifact_repo.list(since=since_past)
    assert len(artifacts_since) == 1

    # Test: until filter (should exclude the artifact)
    until_past = now - timedelta(hours=1)
    artifacts_until = artifact_repo.list(until=until_past)
    assert len(artifacts_until) == 0

    # Test: until filter (should include the artifact)
    until_future = now + timedelta(hours=1)
    artifacts_until_future = artifact_repo.list(until=until_future)
    assert len(artifacts_until_future) == 1


def test_artifact_metadata(artifact_repo: ArtifactRepository, sample_job_id: str):
    """Test artifact with extended metadata"""
    metadata = {
        "execution_time_ms": 1234,
        "model_used": "claude-opus-4",
        "custom_field": "test_value",
    }

    artifact_id = artifact_repo.put(
        kind="issue_snapshot",
        schema_version="v1",
        content={"issue_id": "456"},
        producer_engine="IssueComposerEngine",
        producer_version="v1.0",
        job_id=sample_job_id,
        metadata=metadata,
    )

    # Retrieve and verify
    artifact = artifact_repo.get(artifact_id)
    assert artifact is not None
    assert artifact.metadata is not None
    assert artifact.metadata["execution_time_ms"] == 1234
    assert artifact.metadata["model_used"] == "claude-opus-4"
    assert artifact.metadata["custom_field"] == "test_value"
