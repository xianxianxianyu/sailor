from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter

from backend.app.container import AppContainer
from backend.app.schemas import IngestionRunOut, MainFlowTaskOut

logger = logging.getLogger("sailor")

router = APIRouter(prefix="/tasks", tags=["tasks"])


def mount_task_routes(container: AppContainer) -> APIRouter:
    @router.post("/run-ingestion", response_model=IngestionRunOut)
    def run_ingestion() -> IngestionRunOut:
        logger.info("🔄 开始执行 RSS 抓取任务...")
        result = container.ingestion_service.run()
        logger.info(f"✅ RSS 抓取完成: 新增 {result.new_count}, 更新 {result.updated_count}, 跳过 {result.skipped_count}")
        return IngestionRunOut.model_validate(asdict(result))

    @router.get("/main-flow", response_model=list[MainFlowTaskOut])
    def list_main_flow_tasks() -> list[MainFlowTaskOut]:
        logger.info("获取主流程任务列表")
        tasks = container.task_planner.build_tasks()
        logger.info(f"📋 主流程任务: {len(tasks)} 个")
        return [MainFlowTaskOut.model_validate(asdict(item)) for item in tasks]

    @router.get("/ingestion-status")
    def get_ingestion_status() -> dict:
        """获取抓取状态（供前端轮询）"""
        last_run = container.ingestion_repo.get_last_run()
        if not last_run:
            return {
                "status": "idle",
                "last_run": None,
                "new_count": 0,
                "updated_count": 0,
                "skipped_count": 0,
            }
        return {
            "status": "completed",
            "last_run": last_run.started_at.isoformat() if last_run.started_at else None,
            "new_count": last_run.new_count,
            "updated_count": last_run.updated_count,
            "skipped_count": last_run.skipped_count,
        }

    return router
