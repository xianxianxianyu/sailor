from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter

from backend.app.container import AppContainer
from backend.app.schemas import IngestionRunOut, MainFlowTaskOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def mount_task_routes(container: AppContainer) -> APIRouter:
    @router.post("/run-ingestion", response_model=IngestionRunOut)
    def run_ingestion() -> IngestionRunOut:
        logger.info("开始执行 RSS 抓取任务...")
        result = container.ingestion_service.run()
        logger.info("RSS 抓取完成: 采集 %d, 处理 %d", result.collected_count, result.processed_count)
        return IngestionRunOut.model_validate(asdict(result))

    @router.get("/main-flow", response_model=list[MainFlowTaskOut])
    def list_main_flow_tasks() -> list[MainFlowTaskOut]:
        logger.info("获取主流程任务列表")
        tasks = container.task_planner.build_tasks()
        logger.info("主流程任务: %d 个", len(tasks))
        return [MainFlowTaskOut.model_validate(asdict(item)) for item in tasks]

    return router
