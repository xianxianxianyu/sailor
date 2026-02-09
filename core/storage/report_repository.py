from __future__ import annotations

import json
from datetime import datetime

from core.models import KBReport
from core.storage.db import Database


class KBReportRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, report: KBReport) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO kb_reports (
                    report_id, kb_id, report_type, content_json,
                    resource_count, model, prompt_tokens, completion_tokens,
                    status, error_message, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    content_json=excluded.content_json,
                    resource_count=excluded.resource_count,
                    model=excluded.model,
                    prompt_tokens=excluded.prompt_tokens,
                    completion_tokens=excluded.completion_tokens,
                    status=excluded.status,
                    error_message=excluded.error_message,
                    completed_at=excluded.completed_at
                """,
                (
                    report.report_id,
                    report.kb_id,
                    report.report_type,
                    report.content_json,
                    report.resource_count,
                    report.model,
                    report.prompt_tokens,
                    report.completion_tokens,
                    report.status,
                    report.error_message,
                    report.created_at.isoformat() if report.created_at else datetime.utcnow().isoformat(),
                    report.completed_at.isoformat() if report.completed_at else None,
                ),
            )

    def list_by_kb(self, kb_id: str) -> list[KBReport]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM kb_reports WHERE kb_id = ? ORDER BY created_at DESC",
                (kb_id,),
            ).fetchall()
        return [_row_to_report(row) for row in rows]

    def get_by_id(self, report_id: str) -> KBReport | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM kb_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        return _row_to_report(row) if row else None

    def get_latest_by_type(self, kb_id: str) -> list[KBReport]:
        """获取每种类型的最新报告。"""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM kb_reports
                WHERE kb_id = ? AND status = 'completed'
                AND created_at = (
                    SELECT MAX(created_at) FROM kb_reports r2
                    WHERE r2.kb_id = kb_reports.kb_id
                    AND r2.report_type = kb_reports.report_type
                    AND r2.status = 'completed'
                )
                ORDER BY report_type
                """,
                (kb_id,),
            ).fetchall()
        return [_row_to_report(row) for row in rows]


def _row_to_report(row) -> KBReport:
    return KBReport(
        report_id=row["report_id"],
        kb_id=row["kb_id"],
        report_type=row["report_type"],
        content_json=row["content_json"],
        resource_count=row["resource_count"],
        model=row["model"],
        prompt_tokens=row["prompt_tokens"] or 0,
        completion_tokens=row["completion_tokens"] or 0,
        status=row["status"],
        error_message=row["error_message"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
    )
