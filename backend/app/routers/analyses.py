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

logger = logging.getLogger("sailor")

router = APIRouter(tags=["analyses"])


def mount_analysis_routes(container: AppContainer) -> APIRouter:
    @router.post("/tasks/run-analysis", response_model=RunAnalysisOut)
    def run_analysis(payload: RunAnalysisIn | None = None) -> RunAnalysisOut:
        resource_ids = payload.resource_ids if payload else None
        if resource_ids:
            logger.info(f"🔍 开始分析文章: {len(resource_ids)} 篇")
        else:
            logger.info("🔍 开始分析待处理文章...")
        
        analyzed, failed = container.article_agent.analyze_pending(resource_ids)
        
        logger.info(f"✅ 文章分析完成: 成功 {analyzed}, 失败 {failed}")
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
        logger.info(f"📊 分析状态: pending={summary.get('pending', 0)}, completed={summary.get('completed', 0)}, failed={summary.get('failed', 0)}")
        return AnalysisStatusOut.model_validate(summary)

    return router
