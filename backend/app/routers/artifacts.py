"""Artifact API Router

Endpoints for querying and retrieving artifacts.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas import ArtifactOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _artifact_to_out(a) -> ArtifactOut:
    """Convert Artifact to ArtifactOut"""
    return ArtifactOut(
        artifact_id=a.artifact_id,
        kind=a.kind,
        schema_version=a.schema_version,
        content=a.content,
        content_ref=a.content_ref,
        input_refs=a.input_refs,
        producer=a.producer,
        job_id=a.job_id,
        created_at=a.created_at,
        metadata=a.metadata,
    )


def mount_artifact_routes(container: AppContainer) -> APIRouter:
    """Mount artifact routes"""

    @router.get("/{artifact_id}", response_model=ArtifactOut)
    def get_artifact(artifact_id: str) -> ArtifactOut:
        """Get artifact by ID

        Returns the complete artifact including content.
        """
        artifact = container.artifact_repo.get(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return _artifact_to_out(artifact)

    @router.get("", response_model=list[ArtifactOut])
    def list_artifacts(
        kind: str | None = None,
        job_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ArtifactOut]:
        """List artifacts with filters

        Args:
            kind: Filter by artifact kind (board_bundle, research_bundle, etc.)
            job_id: Filter by job ID
            since: Filter by created_at >= since (ISO datetime)
            until: Filter by created_at < until (ISO datetime)
            limit: Maximum number of results (default 50)
            offset: Number of results to skip (default 0)

        Returns:
            List of artifacts ordered by created_at DESC
        """
        # Parse datetime strings
        since_dt = datetime.fromisoformat(since) if since else None
        until_dt = datetime.fromisoformat(until) if until else None

        artifacts = container.artifact_repo.list(
            kind=kind,
            job_id=job_id,
            since=since_dt,
            until=until_dt,
            limit=limit,
            offset=offset,
        )

        return [_artifact_to_out(a) for a in artifacts]

    @router.get("/latest/{kind}", response_model=ArtifactOut)
    def get_latest_artifact(kind: str) -> ArtifactOut:
        """Get latest artifact of specific kind

        Args:
            kind: Artifact kind (board_bundle, research_bundle, etc.)

        Returns:
            Most recent artifact of the specified kind
        """
        artifact = container.artifact_repo.find_latest_by_kind(kind)
        if not artifact:
            raise HTTPException(
                status_code=404,
                detail=f"No artifacts found for kind: {kind}"
            )
        return _artifact_to_out(artifact)

    return router
