from __future__ import annotations

import json

from fastapi import APIRouter

from backend.app.container import AppContainer
from backend.app.schemas import GenerateReportsIn, KBReportOut

router = APIRouter(prefix="/knowledge-bases", tags=["reports"])


def mount_report_routes(container: AppContainer) -> APIRouter:
    @router.post("/{kb_id}/reports")
    def generate_reports(kb_id: str, payload: GenerateReportsIn | None = None) -> list[KBReportOut]:
        report_types = payload.report_types if payload else None
        reports = container.kb_agent.generate_all(kb_id, report_types)
        return [_to_out(r) for r in reports]

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
