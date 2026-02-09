from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime

from core.agent.base import LLMClient
from core.agent.prompts import build_article_prompt
from core.models import Resource, ResourceAnalysis
from core.storage.analysis_repository import AnalysisRepository
from core.storage.repositories import KnowledgeBaseRepository, ResourceRepository

logger = logging.getLogger(__name__)


class ArticleAnalysisAgent:
    def __init__(
        self,
        llm: LLMClient,
        analysis_repo: AnalysisRepository,
        resource_repo: ResourceRepository,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self.llm = llm
        self.analysis_repo = analysis_repo
        self.resource_repo = resource_repo
        self.kb_repo = kb_repo

    def analyze(self, resource: Resource) -> ResourceAnalysis:
        """分析单篇文章。"""
        # 获取知识库列表供推荐
        kbs = self.kb_repo.list_all()
        kb_list = [asdict(kb) for kb in kbs]

        messages = build_article_prompt(
            title=resource.title,
            text=resource.text or resource.summary,
            kb_list=kb_list,
        )

        try:
            resp = self.llm.chat(messages)
            result = _parse_json_response(resp.content)

            analysis = ResourceAnalysis(
                resource_id=resource.resource_id,
                summary=result.get("summary", ""),
                topics_json=json.dumps(result.get("topics", []), ensure_ascii=False),
                scores_json=json.dumps(result.get("scores", {}), ensure_ascii=False),
                kb_recommendations_json=json.dumps(result.get("kb_recommendations", []), ensure_ascii=False),
                insights_json=json.dumps(result.get("insights", {}), ensure_ascii=False),
                model=resp.model,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                status="completed",
                completed_at=datetime.utcnow(),
            )
            self.analysis_repo.save(analysis)
            return analysis

        except Exception as exc:
            logger.error("分析资源 %s 失败: %s", resource.resource_id, exc)
            analysis = ResourceAnalysis(
                resource_id=resource.resource_id,
                summary="",
                topics_json="[]",
                scores_json="{}",
                kb_recommendations_json="[]",
                insights_json="{}",
                model=self.llm.config.model,
                status="failed",
                error_message=str(exc)[:500],
            )
            self.analysis_repo.save(analysis)
            return analysis

    def analyze_pending(self, resource_ids: list[str] | None = None) -> tuple[int, int]:
        """批量分析 pending 资源，返回 (成功数, 失败数)。"""
        if resource_ids:
            resources = [
                self.resource_repo.get_resource(rid)
                for rid in resource_ids
            ]
            resources = [r for r in resources if r is not None]
        else:
            resources = self.resource_repo.list_resources()

        analyzed = 0
        failed = 0

        for resource in resources:
            # 幂等：已有 completed 分析的跳过
            existing = self.analysis_repo.get_by_resource_id(resource.resource_id)
            if existing and existing.status == "completed":
                continue

            result = self.analyze(resource)
            if result.status == "completed":
                analyzed += 1
            else:
                failed += 1

        return analyzed, failed


def _parse_json_response(content: str) -> dict:
    """解析 LLM 返回的 JSON，处理可能的 markdown 代码块包裹。"""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉首尾的 ``` 行
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
