from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.container import AppContainer
from backend.app.routers.logs import add_log


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
        add_log("INFO", "[trending] 开始生成 trending 报告")
        from core.services.trending import TrendingService
        svc = TrendingService(
            resource_repo=container.resource_repo,
            tag_repo=container.tag_repo,
            tagging_agent=container.tagging_agent,
        )
        report = svc.generate(tag_resources=True)
        add_log("INFO", f"[trending] 完成 trending 报告: {report.total_resources} 资源, {report.total_tags} 标签")
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
        add_log("INFO", "[trending] 开始执行完整 pipeline")
        from core.services.trending import TrendingService

        # Step 1: 抓取
        add_log("INFO", "[trending] [pipeline] Step 1/3: 开始抓取资源")
        ingestion_result = container.ingestion_service.run()
        add_log("INFO", f"[trending] [pipeline] Step 1 完成: 抓取 {ingestion_result.collected_count} 条")

        # Step 2: 打标 + trending
        add_log("INFO", "[trending] [pipeline] Step 2/3: 开始 LLM 打标")
        svc = TrendingService(
            resource_repo=container.resource_repo,
            tag_repo=container.tag_repo,
            tagging_agent=container.tagging_agent,
        )
        report = svc.generate(tag_resources=True)
        add_log("INFO", f"[trending] [pipeline] Step 2 完成: 打标 {report.total_resources} 个资源")

        # Step 3: 生成报告 (已在 Step 2 一起完成)
        add_log("INFO", f"[trending] [pipeline] 完成: 共 {report.total_tags} 个标签分组")

        return PipelineResultOut(
            collected=ingestion_result.collected_count,
            processed=ingestion_result.processed_count,
            tagged=sum(len(g.items) for g in report.groups),
        )

    return router
