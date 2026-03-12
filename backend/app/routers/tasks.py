from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas import MainFlowTaskOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["jobs"])


def mount_task_routes(container: AppContainer) -> APIRouter:
    @router.post("/run-ingestion")
    def run_ingestion() -> None:
        raise HTTPException(status_code=501, detail="run-ingestion 已废弃，请使用 /sources/{id}/run")

    @router.get("/main-flow", response_model=list[MainFlowTaskOut])
    def list_main_flow_tasks() -> list[MainFlowTaskOut]:
        logger.info("获取主流程任务列表")
        tasks = container.task_planner.build_tasks()
        logger.info("主流程任务: %d 个", len(tasks))
        return [MainFlowTaskOut.model_validate(asdict(item)) for item in tasks]

    return router
