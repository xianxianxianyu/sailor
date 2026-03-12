from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, Query, Response

from backend.app.container import AppContainer
from backend.app.schemas import GenerateReportsIn, JobAcceptedOut, KBReportOut
from backend.app.utils import wait_for_job
from core.models import Job

router = APIRouter(prefix="/knowledge-bases", tags=["system"])


def mount_report_routes(container: AppContainer) -> APIRouter:
    @router.post("/{kb_id}/reports", response_model=list[KBReportOut] | JobAcceptedOut)
    def generate_reports(
        kb_id: str,
        response: Response,
        payload: GenerateReportsIn | None = None,
        wait: bool = Query(False),
        timeout: int = Query(300),
    ) -> list[KBReportOut] | JobAcceptedOut:
        report_types = payload.report_types if payload else None

        job_id = uuid.uuid4().hex[:12]
        container.job_repo.create_job(Job(
            job_id=job_id,
            job_type="kb_reports_generate",
            input_json=json.dumps({"kb_id": kb_id, "report_types": report_types}),
        ))

        if not wait:
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status="queued")

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status=result_job.status)
        if result_job.status in ("failed", "cancelled"):
            return JobAcceptedOut(
                job_id=job_id,
                status=result_job.status,
                error_message=result_job.error_message or ("KB reports generation failed" if result_job.status == "failed" else None),
            )

        output = json.loads(result_job.output_json or "{}")
        report_ids = output.get("report_ids") or []
        reports = [container.report_repo.get_by_id(rid) for rid in report_ids]
        return [_to_out(r) for r in reports if r is not None]

    @router.get("/{kb_id}/reports", response_model=list[KBReportOut])
    def list_reports(kb_id: str) -> list[KBReportOut]:
        reports = container.report_repo.list_by_kb(kb_id)
        return [_to_out(r) for r in reports]

    @router.get("/{kb_id}/reports/latest", response_model=list[KBReportOut])
    def get_latest_reports(kb_id: str) -> list[KBReportOut]:
        reports = container.report_repo.get_latest_by_type(kb_id)
        return [_to_out(r) for r in reports]

    return router


def _to_out(report) -> KBReportOut:
    return KBReportOut(
        report_id=report.report_id,
        kb_id=report.kb_id,
        report_type=report.report_type,
        content=json.loads(report.content_json) if report.content_json else {},
        resource_count=report.resource_count,
        model=report.model,
        prompt_tokens=report.prompt_tokens,
        completion_tokens=report.completion_tokens,
        status=report.status,
        error_message=report.error_message,
        created_at=report.created_at,
        completed_at=report.completed_at,
    )
