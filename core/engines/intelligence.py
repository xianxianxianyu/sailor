"""ResourceIntelligenceEngine — unified computation of tags, analysis, and scores."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.article_agent import ArticleAnalysisAgent
from core.agent.tagging_agent import TaggingAgent
from core.storage.analysis_repository import AnalysisRepository
from core.storage.repositories import ResourceRepository
from core.storage.tag_repository import TagRepository

if TYPE_CHECKING:
    from core.runner.handlers import RunContext

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IntelligenceResult:
    resource_id: str
    tags: list[str]
    analysis_status: str
    error: str | None = None


class ResourceIntelligenceEngine:
    """Produces tags + analysis artifacts for a batch of resources.

    Consumers (Trending, KB, QA) call this instead of invoking agents directly.
    """

    def __init__(
        self,
        resource_repo: ResourceRepository,
        tag_repo: TagRepository,
        analysis_repo: AnalysisRepository,
        tagging_agent: TaggingAgent,
        article_agent: ArticleAnalysisAgent,
    ) -> None:
        self.resource_repo = resource_repo
        self.tag_repo = tag_repo
        self.analysis_repo = analysis_repo
        self.tagging_agent = tagging_agent
        self.article_agent = article_agent

    def process(
        self,
        resource_ids: list[str] | None = None,
        ctx: RunContext | None = None,
    ) -> list[IntelligenceResult]:
        """Run tagging + analysis for the given resources (or all if None)."""
        if resource_ids:
            resources = [
                r for r in (self.resource_repo.get_resource(rid) for rid in resource_ids)
                if r is not None
            ]
        else:
            resources = self.resource_repo.list_resources()

        results: list[IntelligenceResult] = []
        for res in resources:
            tags = self._ensure_tags(res.resource_id, res.title, res.text, ctx)
            analysis_status = self._ensure_analysis(res, ctx)
            results.append(IntelligenceResult(
                resource_id=res.resource_id,
                tags=tags,
                analysis_status=analysis_status,
            ))
        return results

    def _ensure_tags(self, resource_id: str, title: str, text: str, ctx: RunContext | None = None) -> list[str]:
        existing = self.tag_repo.get_resource_tags(resource_id)
        if existing:
            return [t.name for t in existing]
        try:
            if ctx is not None:
                return ctx.call_tool(
                    "tagging_agent:tag_resource",
                    {"resource_id": resource_id, "title": title},
                    lambda _req: self.tagging_agent.tag_resource(resource_id, title, text),
                )
            return self.tagging_agent.tag_resource(resource_id, title, text)
        except Exception:
            logger.warning("Tagging failed for %s", resource_id, exc_info=True)
            return []

    def _ensure_analysis(self, resource, ctx: RunContext | None = None) -> str:
        existing = self.analysis_repo.get_by_resource_id(resource.resource_id)
        if existing and existing.status == "completed":
            return "completed"
        try:
            if ctx is not None:
                result = ctx.call_tool(
                    "article_agent:analyze",
                    {"resource_id": resource.resource_id},
                    lambda _req: self.article_agent.analyze(resource),
                )
                return result.status
            result = self.article_agent.analyze(resource)
            return result.status
        except Exception:
            logger.warning("Analysis failed for %s", resource.resource_id, exc_info=True)
            return "failed"
