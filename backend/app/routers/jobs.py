from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.app.container import AppContainer
from backend.app.schemas import JobCancelOut, JobOut, ProvenanceEventOut
from core.models import ProvenanceEvent


def mount_job_routes(container: AppContainer) -> APIRouter:
    router = APIRouter(prefix="/jobs", tags=["jobs"])

    @router.get("/{job_id}", response_model=JobOut)
    def get_job(job_id: str) -> JobOut:
        job = container.job_repo.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobOut(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            input_json=job.input_json,
            output_json=job.output_json,
            error_class=job.error_class,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            metadata=job.metadata,
        )

    @router.post("/{job_id}/cancel", response_model=JobCancelOut)
    def cancel_job(job_id: str, response: Response) -> JobCancelOut:
        job = container.job_repo.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status == "queued":
            cancelled = container.job_repo.cancel_job(job_id)
            if not cancelled:
                raise HTTPException(status_code=409, detail="Job can no longer be cancelled")
            container.job_repo.append_event(ProvenanceEvent(
                event_id=uuid.uuid4().hex[:12],
                run_id=job_id,
                event_type="JobCancelled",
                actor="user",
                entity_refs={"job_id": job_id},
                payload={"reason": "user_requested"},
            ))
            return JobCancelOut(job_id=cancelled.job_id, status=cancelled.status, cancel_requested=True)

        if job.status == "running":
            updated = container.job_repo.request_cancel(job_id)
            if not updated:
                raise HTTPException(status_code=409, detail="Job can no longer be cancelled")
            response.status_code = 202
            container.job_repo.append_event(ProvenanceEvent(
                event_id=uuid.uuid4().hex[:12],
                run_id=job_id,
                event_type="JobCancelRequested",
                actor="user",
                entity_refs={"job_id": job_id},
                payload={"status": updated.status},
            ))
            return JobCancelOut(job_id=updated.job_id, status=updated.status, cancel_requested=True)

        if job.status == "cancelled":
            return JobCancelOut(job_id=job.job_id, status=job.status, cancel_requested=True)

        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job in status '{job.status}'",
        )

    @router.get("/{job_id}/events", response_model=list[ProvenanceEventOut])
    def list_job_events(job_id: str) -> list[ProvenanceEventOut]:
        job = container.job_repo.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        events = container.job_repo.list_events(job_id)
        return [
            ProvenanceEventOut(
                event_id=e.event_id,
                run_id=e.run_id,
                event_type=e.event_type,
                actor=e.actor,
                entity_refs=e.entity_refs,
                payload=e.payload,
                ts=e.ts,
            )
            for e in events
        ]

    return router
