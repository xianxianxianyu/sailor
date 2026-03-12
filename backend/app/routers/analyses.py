from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Response

from backend.app.container import AppContainer
from backend.app.schemas import (
    AnalysisStatusOut,
    JobAcceptedOut,
    ResourceAnalysisOut,
    RunAnalysisIn,
    RunAnalysisOut,
)
from backend.app.utils import wait_for_job
from core.models import Job

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


def _analysis_to_out(analysis) -> ResourceAnalysisOut:
    return ResourceAnalysisOut(
        resource_id=analysis.resource_id,
        summary=analysis.summary,
        topics=json.loads(analysis.topics_json),
        scores=json.loads(analysis.scores_json),
        kb_recommendations=json.loads(analysis.kb_recommendations_json),
        insights=json.loads(analysis.insights_json),
        model=analysis.model,
        prompt_tokens=analysis.prompt_tokens,
        completion_tokens=analysis.completion_tokens,
        status=analysis.status,
        error_message=analysis.error_message,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
    )


def mount_analysis_routes(container: AppContainer) -> APIRouter:
    @router.post("/resources/{resource_id}/analyze", response_model=ResourceAnalysisOut | JobAcceptedOut)
    def analyze_resource(
        resource_id: str,
        response: Response,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> ResourceAnalysisOut | JobAcceptedOut:
        """单条 LLM 分析（幂等）：enqueue job；可选 wait=true 等待完成。"""
        existing = container.analysis_repo.get_by_resource_id(resource_id)
        if existing and existing.status == "completed":
            return _analysis_to_out(existing)

        # 获取文章
        resource = container.resource_repo.get_resource(resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="文章不存在")

        # 内容过短跳过
        text = resource.text or ""
        if len(text) < 20:
            raise HTTPException(status_code=422, detail="内容过短，无法进行 LLM 分析")

        # Enqueue job — worker executes
        job_id = uuid.uuid4().hex[:12]
        container.job_repo.create_job(Job(
            job_id=job_id,
            job_type="resource_analyze",
            input_json=json.dumps({"resource_id": resource_id}),
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
                error_message=result_job.error_message or ("LLM 分析失败" if result_job.status == "failed" else None),
            )

        analysis = container.analysis_repo.get_by_resource_id(resource_id)
        if not analysis:
            raise HTTPException(status_code=500, detail={
                "job_id": job_id,
                "status": "succeeded",
                "error_message": "分析已完成但未找到分析结果",
            })
        return _analysis_to_out(analysis)

    @router.post("/tasks/run-analysis", response_model=RunAnalysisOut | JobAcceptedOut)
    def run_analysis(
        response: Response,
        payload: RunAnalysisIn | None = None,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> RunAnalysisOut | JobAcceptedOut:
        """批量分析（enqueue job）；可选 wait=true 等待完成。"""
        resource_ids = payload.resource_ids if payload else None

        job_id = uuid.uuid4().hex[:12]
        container.job_repo.create_job(Job(
            job_id=job_id,
            job_type="analysis_run",
            input_json=json.dumps({"resource_ids": resource_ids}),
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
                error_message=result_job.error_message or ("批量分析失败" if result_job.status == "failed" else None),
            )

        output = json.loads(result_job.output_json or "{}")
        return RunAnalysisOut(
            analyzed_count=int(output.get("analyzed_count", 0)),
            failed_count=int(output.get("failed_count", 0)),
        )

    @router.get("/resources/{resource_id}/analysis", response_model=ResourceAnalysisOut)
    def get_resource_analysis(resource_id: str) -> ResourceAnalysisOut:
        logger.info(f"获取文章分析结果: {resource_id}")
        analysis = container.analysis_repo.get_by_resource_id(resource_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="分析结果不存在")
        return _analysis_to_out(analysis)

    @router.get("/analyses/status", response_model=AnalysisStatusOut)
    def get_analysis_status() -> AnalysisStatusOut:
        summary = container.analysis_repo.get_status_summary()
        logger.info("分析状态: pending=%d, completed=%d, failed=%d", summary.get('pending', 0), summary.get('completed', 0), summary.get('failed', 0))
        return AnalysisStatusOut.model_validate(summary)

    return router
