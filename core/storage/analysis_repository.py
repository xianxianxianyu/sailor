from __future__ import annotations

import json
from datetime import datetime

from core.models import ResourceAnalysis
from core.storage.db import Database


class AnalysisRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, analysis: ResourceAnalysis) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO resource_analyses (
                    resource_id, summary, topics_json, scores_json,
                    kb_recommendations_json, insights_json, model,
                    prompt_tokens, completion_tokens, status,
                    error_message, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(resource_id) DO UPDATE SET
                    summary=excluded.summary,
                    topics_json=excluded.topics_json,
                    scores_json=excluded.scores_json,
                    kb_recommendations_json=excluded.kb_recommendations_json,
                    insights_json=excluded.insights_json,
                    model=excluded.model,
                    prompt_tokens=excluded.prompt_tokens,
                    completion_tokens=excluded.completion_tokens,
                    status=excluded.status,
                    error_message=excluded.error_message,
                    completed_at=excluded.completed_at
                """,
                (
                    analysis.resource_id,
                    analysis.summary,
                    analysis.topics_json,
                    analysis.scores_json,
                    analysis.kb_recommendations_json,
                    analysis.insights_json,
                    analysis.model,
                    analysis.prompt_tokens,
                    analysis.completion_tokens,
                    analysis.status,
                    analysis.error_message,
                    analysis.created_at.isoformat() if analysis.created_at else datetime.utcnow().isoformat(),
                    analysis.completed_at.isoformat() if analysis.completed_at else None,
                ),
            )

    def get_by_resource_id(self, resource_id: str) -> ResourceAnalysis | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM resource_analyses WHERE resource_id = ?",
                (resource_id,),
            ).fetchone()
        return _row_to_analysis(row) if row else None

    def list_pending(self) -> list[ResourceAnalysis]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM resource_analyses WHERE status = 'pending'"
            ).fetchall()
        return [_row_to_analysis(row) for row in rows]

    def get_status_summary(self) -> dict[str, int]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM resources) as total,
                    (SELECT COUNT(*) FROM resource_analyses WHERE status = 'pending') as pending,
                    (SELECT COUNT(*) FROM resource_analyses WHERE status = 'completed') as completed,
                    (SELECT COUNT(*) FROM resource_analyses WHERE status = 'failed') as failed
                """
            ).fetchone()
        return {
            "total": rows["total"],
            "pending": rows["pending"],
            "completed": rows["completed"],
            "failed": rows["failed"],
        }


def _row_to_analysis(row) -> ResourceAnalysis:
    return ResourceAnalysis(
        resource_id=row["resource_id"],
        summary=row["summary"],
        topics_json=row["topics_json"],
        scores_json=row["scores_json"],
        kb_recommendations_json=row["kb_recommendations_json"],
        insights_json=row["insights_json"],
        model=row["model"],
        prompt_tokens=row["prompt_tokens"] or 0,
        completion_tokens=row["completion_tokens"] or 0,
        status=row["status"],
        error_message=row["error_message"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
    )
