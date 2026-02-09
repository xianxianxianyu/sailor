from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from core.agent.base import LLMClient
from core.agent.prompts import build_kb_analysis_prompt
from core.models import KBReport
from core.storage.analysis_repository import AnalysisRepository
from core.storage.report_repository import KBReportRepository
from core.storage.repositories import KnowledgeBaseRepository, ResourceRepository

logger = logging.getLogger(__name__)

REPORT_TYPES = ("cluster", "association", "summary")


class KBClusterAgent:
    def __init__(
        self,
        llm: LLMClient,
        report_repo: KBReportRepository,
        analysis_repo: AnalysisRepository,
        resource_repo: ResourceRepository,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self.llm = llm
        self.report_repo = report_repo
        self.analysis_repo = analysis_repo
        self.resource_repo = resource_repo
        self.kb_repo = kb_repo

    def generate_report(self, kb_id: str, report_type: str) -> KBReport:
        """生成单种类型的 KB 报告。"""
        articles = self._build_article_summaries(kb_id)
        if len(articles) < 3:
            raise ValueError(f"KB {kb_id} 内文章不足 3 篇（当前 {len(articles)} 篇），无法生成报告")

        # 如果超过 30 篇，只取前 30 篇
        batch = articles[:30]

        messages = build_kb_analysis_prompt(report_type, batch)

        report_id = f"rpt_{uuid.uuid4().hex[:12]}"

        try:
            resp = self.llm.chat(messages, max_tokens=2000)
            content = _parse_json_response(resp.content)

            report = KBReport(
                report_id=report_id,
                kb_id=kb_id,
                report_type=report_type,
                content_json=json.dumps(content, ensure_ascii=False),
                resource_count=len(batch),
                model=resp.model,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                status="completed",
                completed_at=datetime.utcnow(),
            )
            self.report_repo.save(report)
            return report

        except Exception as exc:
            logger.error("生成 KB %s 的 %s 报告失败: %s", kb_id, report_type, exc)
            report = KBReport(
                report_id=report_id,
                kb_id=kb_id,
                report_type=report_type,
                content_json="{}",
                resource_count=0,
                model=self.llm.config.model,
                status="failed",
                error_message=str(exc)[:500],
            )
            self.report_repo.save(report)
            return report

    def generate_all(self, kb_id: str, report_types: list[str] | None = None) -> list[KBReport]:
        """生成全部（或指定类型的）报告。"""
        types = report_types or list(REPORT_TYPES)
        reports = []
        for rt in types:
            if rt not in REPORT_TYPES:
                continue
            report = self.generate_report(kb_id, rt)
            reports.append(report)
        return reports

    def _build_article_summaries(self, kb_id: str) -> list[dict]:
        """构建 KB 内文章的摘要列表（用于 LLM 输入）。"""
        with self.kb_repo.db.connect() as conn:
            rows = conn.execute(
                "SELECT resource_id FROM kb_items WHERE kb_id = ?",
                (kb_id,),
            ).fetchall()

        articles = []
        for row in rows:
            resource_id = row["resource_id"]
            resource = self.resource_repo.get_resource(resource_id)
            if not resource:
                continue

            # 优先使用 Agent 1 的分析结果
            analysis = self.analysis_repo.get_by_resource_id(resource_id)
            if analysis and analysis.status == "completed":
                summary = analysis.summary
                topics = json.loads(analysis.topics_json)
            else:
                summary = resource.summary
                topics = resource.topics

            articles.append({
                "resource_id": resource_id,
                "title": resource.title,
                "summary": summary,
                "topics": topics,
            })

        return articles


def _parse_json_response(content: str) -> dict:
    """解析 LLM 返回的 JSON。"""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
