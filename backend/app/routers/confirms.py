from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas import ConfirmActionIn, PendingConfirmOut

router = APIRouter(prefix="/confirms", tags=["confirms"])


def _confirm_to_out(pc) -> PendingConfirmOut:
    return PendingConfirmOut(
        confirm_id=pc.confirm_id,
        job_id=pc.job_id,
        action_type=pc.action_type,
        payload=json.loads(pc.payload_json or "{}"),
        status=pc.status,
        created_at=pc.created_at,
        resolved_at=pc.resolved_at,
    )


def mount_confirm_routes(container: AppContainer) -> APIRouter:

    @router.get("", response_model=list[PendingConfirmOut])
    def list_pending(status: str = "pending", limit: int = 50):
        confirms = container.job_repo.list_confirms(status=status, limit=max(1, min(limit, 200)))
        return [_confirm_to_out(pc) for pc in confirms]

    @router.get("/{confirm_id}", response_model=PendingConfirmOut)
    def get_confirm(confirm_id: str):
        pc = container.job_repo.get_confirm(confirm_id)
        if not pc:
            raise HTTPException(status_code=404, detail="Confirm not found")
        return _confirm_to_out(pc)

    @router.post("/{confirm_id}/resolve", response_model=PendingConfirmOut)
    def resolve_confirm(confirm_id: str, payload: ConfirmActionIn):
        if payload.action not in ("approve", "reject"):
            raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

        pc = container.job_repo.get_confirm(confirm_id)
        if not pc:
            raise HTTPException(status_code=404, detail="Confirm not found")
        if pc.status != "pending":
            raise HTTPException(status_code=409, detail=f"Confirm already {pc.status}")

        status = "approved" if payload.action == "approve" else "rejected"
        resolved = container.job_repo.resolve_confirm(confirm_id, status)
        if not resolved:
            raise HTTPException(status_code=500, detail="Failed to resolve confirm")

        # On approve, create a job to execute the pending action
        if payload.action == "approve":
            confirm_payload = json.loads(resolved.payload_json or "{}")
            job_type = confirm_payload.get("job_type")
            input_json = confirm_payload.get("input_json")
            if job_type and input_json:
                import uuid
                from core.models import Job
                job = container.job_repo.create_job(Job(
                    job_id=uuid.uuid4().hex[:12],
                    job_type=job_type,
                    input_json=json.dumps(input_json) if isinstance(input_json, dict) else input_json,
                ))
                container.job_runner.run(job.job_id)

        return _confirm_to_out(resolved)

    return router
