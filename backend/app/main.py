from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logging_config import setup_logging

setup_logging()

from backend.app.container import build_container
from backend.app.middleware import AccessLogMiddleware
from backend.app.routers.knowledge_bases import mount_knowledge_base_routes
from backend.app.routers.resources import mount_resources_routes
from backend.app.routers.tasks import mount_task_routes
from backend.app.routers.analyses import mount_analysis_routes
from backend.app.routers.reports import mount_report_routes
from backend.app.routers.sources import mount_source_routes
from backend.app.routers.boards import mount_board_routes
from backend.app.routers.follows import mount_follow_routes
from backend.app.routers.artifacts import mount_artifact_routes
from backend.app.routers.paper_sources import mount_paper_routes
from backend.app.routers.research_programs import mount_research_program_routes
from backend.app.routers.tags import mount_tag_routes
from backend.app.routers.logs import mount_log_routes
from backend.app.routers.settings import mount_settings_routes
from backend.app.routers.sniffer import mount_sniffer_routes
from backend.app.routers.confirms import mount_confirm_routes
from backend.app.routers.jobs import mount_job_routes
from backend.app.routers.kg_graph import mount_kg_graph_routes

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
container = build_container(PROJECT_ROOT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("Sailor Backend started")
    logger.info(f"   project root: {PROJECT_ROOT}")
    logger.info("=" * 50)
    yield


app = FastAPI(
    title="Sailor",
    version="0.1.0",
    description="自动化信息聚合与出刊平台 — Follow 系统",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "follows", "description": "Follow 管理与运行"},
        {"name": "boards", "description": "Board 榜单管理"},
        {"name": "research", "description": "Research Program 管理"},
        {"name": "artifacts", "description": "Artifact 存储与查询"},
        {"name": "sources", "description": "数据源管理"},
        {"name": "jobs", "description": "Job 执行与监控"},
        {"name": "system", "description": "系统管理"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=container.settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AccessLogMiddleware)

app.include_router(mount_resources_routes(container))
app.include_router(mount_knowledge_base_routes(container))
app.include_router(mount_task_routes(container))
app.include_router(mount_source_routes(container))
app.include_router(mount_job_routes(container))
for paper_router in mount_paper_routes(container):
    app.include_router(paper_router)
app.include_router(mount_research_program_routes(container))
for board_router in mount_board_routes(container):
    app.include_router(board_router)
app.include_router(mount_follow_routes(container))
app.include_router(mount_artifact_routes(container))
app.include_router(mount_analysis_routes(container))
app.include_router(mount_report_routes(container))
app.include_router(mount_tag_routes(container))
app.include_router(mount_log_routes(container))
app.include_router(mount_settings_routes(container))
app.include_router(mount_sniffer_routes(container))
app.include_router(mount_confirm_routes(container))
app.include_router(mount_kg_graph_routes(container))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
