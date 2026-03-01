from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.container import AppContainer
from core.models import Job

logger = logging.getLogger(__name__)

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
    job_id: str | None = None


def mount_trending_routes(container: AppContainer) -> APIRouter:
    @router.post("/generate", response_model=TrendingReportOut)
    def generate_trending() -> TrendingReportOut:
        logger.info("[trending] 开始生成 trending 报告")
        from core.services.trending import TrendingService
        svc = TrendingService(
            resource_repo=container.resource_repo,
            tag_repo=container.tag_repo,
            tagging_agent=container.tagging_agent,
        )
        report = svc.generate(tag_resources=True)
        logger.info("[trending] 完成 trending 报告: %d 资源, %d 标签", report.total_resources, report.total_tags)
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
        """一键执行完整 pipeline: 抓取 → 打标 → 生成 trending（通过 job 编排）"""
        logger.info("[trending] 开始执行完整 pipeline (job orchestration)")

        # Step 1: 抓取 via job
        logger.info("[trending] [pipeline] Step 1/3: 开始抓取资源 (ingestion job)")
        ingestion_job = container.job_repo.create_job(Job(
            job_id=uuid.uuid4().hex[:12],
            job_type="ingestion",
            input_json=json.dumps({}),
        ))
        ingestion_result_job = container.job_runner.run(ingestion_job.job_id)
        ingestion_output = json.loads(ingestion_result_job.output_json or "{}") if ingestion_result_job.output_json else {}
        collected_count = ingestion_output.get("collected_count", 0)
        processed_count = ingestion_output.get("processed_count", 0)
        logger.info("[trending] [pipeline] Step 1 完成: 抓取 %d 条", collected_count)

        # Step 2: 打标 via job
        logger.info("[trending] [pipeline] Step 2/3: 开始 LLM 打标 (batch_tag job)")
        tag_job = container.job_repo.create_job(Job(
            job_id=uuid.uuid4().hex[:12],
            job_type="batch_tag",
            input_json=json.dumps({}),
        ))
        tag_result_job = container.job_runner.run(tag_job.job_id)
        tag_output = json.loads(tag_result_job.output_json or "{}") if tag_result_job.output_json else {}
        tagged_count = tag_output.get("tagged", 0)
        logger.info("[trending] [pipeline] Step 2 完成: 打标 %d 个资源", tagged_count)

        # Step 3: 生成 trending via job
        logger.info("[trending] [pipeline] Step 3/3: 生成 trending 报告")
        trending_job = container.job_repo.create_job(Job(
            job_id=uuid.uuid4().hex[:12],
            job_type="trending_generate",
            input_json=json.dumps({}),
        ))
        trending_result_job = container.job_runner.run(trending_job.job_id)
        logger.info("[trending] [pipeline] 完成")

        return PipelineResultOut(
            collected=collected_count,
            processed=processed_count,
            tagged=tagged_count,
            job_id=trending_result_job.job_id,
        )

    return router
