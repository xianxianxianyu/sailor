from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.container import AppContainer


router = APIRouter(prefix="/trending", tags=["trending"])


class TrendingItemOut(BaseModel):
    resource_id: str
    title: str
    original_url: str
    summary: str
    tags: list[str]
    source: str


class TrendingGroupOut(BaseModel):
    tag_name: str
    tag_color: str
    items: list[TrendingItemOut]


class TrendingReportOut(BaseModel):
    groups: list[TrendingGroupOut]
    total_resources: int
    total_tags: int


class PipelineResultOut(BaseModel):
    collected: int
    processed: int
    tagged: int


def mount_trending_routes(container: AppContainer) -> APIRouter:
    @router.post("/generate", response_model=TrendingReportOut)
    def generate_trending() -> TrendingReportOut:
        from core.services.trending import TrendingService
        svc = TrendingService(
            resource_repo=container.resource_repo,
            tag_repo=container.tag_repo,
            tagging_agent=container.tagging_agent,
        )
        report = svc.generate(tag_resources=True)
        return TrendingReportOut(
            groups=[TrendingGroupOut(**asdict(g)) for g in report.groups],
            total_resources=report.total_resources,
            total_tags=report.total_tags,
        )

    @router.get("", response_model=TrendingReportOut)
    def get_trending() -> TrendingReportOut:
        """获取当前 trending（不触发 LLM 打标）"""
        from core.services.trending import TrendingService
        svc = TrendingService(
            resource_repo=container.resource_repo,
            tag_repo=container.tag_repo,
            tagging_agent=container.tagging_agent,
        )
        report = svc.generate(tag_resources=False)
        return TrendingReportOut(
            groups=[TrendingGroupOut(**asdict(g)) for g in report.groups],
            total_resources=report.total_resources,
            total_tags=report.total_tags,
        )

    @router.post("/pipeline", response_model=PipelineResultOut)
    def run_full_pipeline() -> PipelineResultOut:
        """一键执行完整 pipeline: 抓取 → 打标 → 生成 trending"""
        from core.services.trending import TrendingService

        # Step 1: 抓取
        ingestion_result = container.ingestion_service.run()

        # Step 2: 打标 + trending
        svc = TrendingService(
            resource_repo=container.resource_repo,
            tag_repo=container.tag_repo,
            tagging_agent=container.tagging_agent,
        )
        report = svc.generate(tag_resources=True)

        return PipelineResultOut(
            collected=ingestion_result.collected_count,
            processed=ingestion_result.processed_count,
            tagged=sum(len(g.items) for g in report.groups),
        )

    return router
