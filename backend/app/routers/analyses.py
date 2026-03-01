from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas import (
    AnalysisStatusOut,
    ResourceAnalysisOut,
    RunAnalysisIn,
    RunAnalysisOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyses"])


def mount_analysis_routes(container: AppContainer) -> APIRouter:
    @router.post("/resources/{resource_id}/analyze", response_model=ResourceAnalysisOut)
    def analyze_resource(resource_id: str) -> dict:
        """单条 LLM 分析（幂等）：已完成直接返回，内容过短跳过，否则调 LLM。"""
        # 幂等：已完成直接返回
        existing = container.analysis_repo.get_by_resource_id(resource_id)
        if existing and existing.status == "completed":
            return ResourceAnalysisOut(
                resource_id=existing.resource_id,
                summary=existing.summary,
                topics=json.loads(existing.topics_json),
                scores=json.loads(existing.scores_json),
                kb_recommendations=json.loads(existing.kb_recommendations_json),
                insights=json.loads(existing.insights_json),
                model=existing.model,
                prompt_tokens=existing.prompt_tokens,
                completion_tokens=existing.completion_tokens,
                status=existing.status,
                error_message=existing.error_message,
                created_at=existing.created_at,
                completed_at=existing.completed_at,
            )

        # 获取文章
        resource = container.resource_repo.get_resource(resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="文章不存在")

        # 内容过短跳过
        text = resource.text or ""
        if len(text) < 20:
            raise HTTPException(status_code=422, detail="内容过短，无法进行 LLM 分析")

        # 调用 LLM 分析
        try:
            analysis = container.article_agent.analyze(resource)
        except Exception as exc:
            logger.error("LLM 分析失败 resource_id=%s: %s", resource_id, exc)
            raise HTTPException(status_code=500, detail=f"LLM 分析失败: {exc}") from exc

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

    @router.post("/tasks/run-analysis", response_model=RunAnalysisOut)
    def run_analysis(payload: RunAnalysisIn | None = None) -> RunAnalysisOut:
        resource_ids = payload.resource_ids if payload else None
        if resource_ids:
            logger.info("开始分析文章: %d 篇", len(resource_ids))
        else:
            logger.info("开始分析待处理文章...")
        
        analyzed, failed = container.article_agent.analyze_pending(resource_ids)
        
        logger.info("文章分析完成: 成功 %d, 失败 %d", analyzed, failed)
        return RunAnalysisOut(analyzed_count=analyzed, failed_count=failed)

    @router.get("/resources/{resource_id}/analysis", response_model=ResourceAnalysisOut)
    def get_resource_analysis(resource_id: str) -> ResourceAnalysisOut:
        logger.info(f"获取文章分析结果: {resource_id}")
        analysis = container.analysis_repo.get_by_resource_id(resource_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="分析结果不存在")
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

    @router.get("/analyses/status", response_model=AnalysisStatusOut)
    def get_analysis_status() -> AnalysisStatusOut:
        summary = container.analysis_repo.get_status_summary()
        logger.info("分析状态: pending=%d, completed=%d, failed=%d", summary.get('pending', 0), summary.get('completed', 0), summary.get('failed', 0))
        return AnalysisStatusOut.model_validate(summary)

    return router
