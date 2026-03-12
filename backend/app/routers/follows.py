"""Follow API Router

Follow CRUD + execution endpoints
"""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Response

from backend.app.container import AppContainer
from backend.app.schemas_follow import (
    CreateFollowIn,
    FollowOut,
    FollowRunJobOut,
    IssueSnapshotOut,
    TriggerFollowRunIn,
    UpdateFollowIn,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/follows", tags=["follows"])


def _follow_to_out(f) -> FollowOut:
    """Convert Follow model to output schema"""
    return FollowOut(
        follow_id=f.follow_id,
        name=f.name,
        description=f.description,
        board_ids=f.board_ids or [],
        research_program_ids=f.research_program_ids or [],
        window_policy=f.window_policy,
        schedule_minutes=f.schedule_minutes,
        enabled=f.enabled,
        last_run_at=f.last_run_at,
        error_count=f.error_count,
        last_error=f.last_error,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


def mount_follow_routes(container: AppContainer) -> APIRouter:
    """Mount follow routes"""

    # ========== CRUD Endpoints ==========

    @router.get("", response_model=list[FollowOut])
    def list_follows(
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FollowOut]:
        """List all Follows"""
        follows = container.follow_repo.list_follows(
            enabled=enabled,
            limit=limit,
            offset=offset,
        )
        return [_follow_to_out(f) for f in follows]

    @router.post("", response_model=FollowOut)
    def create_follow(data: CreateFollowIn) -> FollowOut:
        """Create a new Follow"""
        follow = container.follow_repo.upsert_follow(
            name=data.name,
            description=data.description,
            board_ids=data.board_ids,
            research_program_ids=data.research_program_ids,
            window_policy=data.window_policy,
            schedule_minutes=data.schedule_minutes,
            enabled=data.enabled,
        )
        return _follow_to_out(follow)

    @router.get("/{follow_id}", response_model=FollowOut)
    def get_follow(follow_id: str) -> FollowOut:
        """Get Follow details"""
        follow = container.follow_repo.get_follow(follow_id)
        if not follow:
            raise HTTPException(status_code=404, detail="Follow not found")
        return _follow_to_out(follow)

    @router.patch("/{follow_id}", response_model=FollowOut)
    def update_follow(follow_id: str, data: UpdateFollowIn) -> FollowOut:
        """Update Follow"""
        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.board_ids is not None:
            updates["board_ids"] = data.board_ids
        if data.research_program_ids is not None:
            updates["research_program_ids"] = data.research_program_ids
        if data.window_policy is not None:
            updates["window_policy"] = data.window_policy
        if data.schedule_minutes is not None:
            updates["schedule_minutes"] = data.schedule_minutes
        if data.enabled is not None:
            updates["enabled"] = data.enabled

        follow = container.follow_repo.update_follow(follow_id, **updates)
        if not follow:
            raise HTTPException(status_code=404, detail="Follow not found")
        return _follow_to_out(follow)

    @router.delete("/{follow_id}")
    def delete_follow(follow_id: str) -> dict:
        """Delete Follow"""
        deleted = container.follow_repo.delete_follow(follow_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Follow not found")
        return {"status": "deleted", "follow_id": follow_id}

    # ========== Execution Endpoints ==========

    @router.post("/{follow_id}/run", response_model=FollowRunJobOut)
    def trigger_follow_run(
        follow_id: str,
        response: Response,
        body: TriggerFollowRunIn | None = None,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> FollowRunJobOut:
        """Trigger a Follow run"""
        from backend.app.utils import wait_for_job
        window = body.window if body else None

        follow = container.follow_repo.get_follow(follow_id)
        if not follow:
            raise HTTPException(status_code=404, detail="Follow not found")

        input_data: dict = {"follow_id": follow_id}
        if window:
            input_data["window"] = window

        if window:
            window_key = f"{window['since']}:{window['until']}"
        else:
            window_key = uuid.uuid4().hex[:12]
        idempotency_key = f"follow_run:{follow_id}:{window_key}"

        job_id, is_new = container.job_repo.create_job_idempotent(
            job_type="follow_run",
            idempotency_key=idempotency_key,
            input_json=input_data,
        )

        # If existing job failed/queued, reset to queued so worker picks it up
        if not is_new:
            existing = container.job_repo.get_job(job_id)
            if existing and existing.status not in ("succeeded", "running", "queued"):
                container.job_repo.update_status(job_id, "queued")

        logger.info("[follow-api] Enqueued follow_run job_id=%s follow_id=%s is_new=%s",
                    job_id, follow_id, is_new)

        if not wait:
            job = container.job_repo.get_job(job_id)
            return FollowRunJobOut(
                job_id=job.job_id,
                follow_id=follow_id,
                status=job.status,
                error_message=job.error_message,
            )

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202

        return FollowRunJobOut(
            job_id=result_job.job_id,
            follow_id=follow_id,
            status=result_job.status,
            error_message=result_job.error_message,
        )

    @router.get("/{follow_id}/issues/latest", response_model=IssueSnapshotOut | None)
    def get_latest_issue(follow_id: str) -> IssueSnapshotOut | None:
        """Get the latest IssueSnapshot for a Follow"""
        # Query artifacts for issue_snapshot kind
        artifacts = container.artifact_repo.list(
            kind="issue_snapshot",
            limit=100,
        )

        # Filter by follow_id and find most recent
        latest = None
        for artifact in artifacts:
            metadata = artifact.metadata or {}
            if metadata.get("follow_id") == follow_id:
                if not latest or artifact.created_at > latest.created_at:
                    latest = artifact

        if not latest:
            return None

        # Parse artifact data
        content = latest.content or {}
        metadata = latest.metadata or {}

        return IssueSnapshotOut(
            issue_id=latest.artifact_id,
            follow_id=metadata.get("follow_id", follow_id),
            window=metadata.get("window", {}),
            sections=content.get("sections", []),
            metadata=metadata,
            created_at=latest.created_at,
        )

    @router.get("/{follow_id}/issues", response_model=list[IssueSnapshotOut])
    def list_issues(
        follow_id: str,
        limit: int = 10,
    ) -> list[IssueSnapshotOut]:
        """List IssueSnapshot history for a Follow"""
        # Query artifacts
        artifacts = container.artifact_repo.list(
            kind="issue_snapshot",
            limit=100,
        )

        # Filter by follow_id
        results = []
        for artifact in artifacts:
            metadata = artifact.metadata or {}
            if metadata.get("follow_id") == follow_id:
                content = artifact.content or {}
                results.append(IssueSnapshotOut(
                    issue_id=artifact.artifact_id,
                    follow_id=metadata.get("follow_id", follow_id),
                    window=metadata.get("window", {}),
                    sections=content.get("sections", []),
                    metadata=metadata,
                    created_at=artifact.created_at,
                ))

        # Sort by created_at descending
        results.sort(key=lambda x: x.created_at, reverse=True)

        return results[:limit]

    return router
