from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from backend.app.container import AppContainer
from backend.app.schemas import IngestionRunOut, MainFlowTaskOut


router = APIRouter(prefix="/tasks", tags=["tasks"])


def mount_task_routes(container: AppContainer) -> APIRouter:
    @router.post("/run-ingestion", response_model=IngestionRunOut)
    def run_ingestion() -> IngestionRunOut:
        result = container.ingestion_service.run()
        return IngestionRunOut.model_validate(asdict(result))

    @router.get("/main-flow", response_model=list[MainFlowTaskOut])
    def list_main_flow_tasks() -> list[MainFlowTaskOut]:
        tasks = container.task_planner.build_tasks()
        return [MainFlowTaskOut.model_validate(asdict(item)) for item in tasks]

    return router
