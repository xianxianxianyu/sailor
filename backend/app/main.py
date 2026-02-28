from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.container import build_container
from backend.app.routers.knowledge_bases import mount_knowledge_base_routes
from backend.app.routers.resources import mount_resources_routes
from backend.app.routers.tasks import mount_task_routes
from backend.app.routers.feeds import mount_feed_routes
from backend.app.routers.analyses import mount_analysis_routes
from backend.app.routers.reports import mount_report_routes
from backend.app.routers.sources import mount_source_routes
from backend.app.routers.tags import mount_tag_routes
from backend.app.routers.trending import mount_trending_routes
from backend.app.routers.logs import mount_log_routes
from backend.app.routers.settings import mount_settings_routes

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

# 强制安装日志处理器到 root logger（在 basicConfig 之后）
from backend.app.routers.logs import LogHandler, add_log
_root = logging.getLogger()
if not any(isinstance(h, LogHandler) for h in _root.handlers):
    _h = LogHandler()
    _h.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    _root.addHandler(_h)

logger = logging.getLogger("sailor")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
container = build_container(PROJECT_ROOT)

app = FastAPI(title="Sailor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=container.settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mount_resources_routes(container))
app.include_router(mount_knowledge_base_routes(container))
app.include_router(mount_task_routes(container))
app.include_router(mount_feed_routes(container))
app.include_router(mount_source_routes(container))
app.include_router(mount_analysis_routes(container))
app.include_router(mount_report_routes(container))
app.include_router(mount_tag_routes(container))
app.include_router(mount_trending_routes(container))
app.include_router(mount_log_routes(container))
app.include_router(mount_settings_routes(container))


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("🚀 Sailor Backend 启动")
    logger.info(f"   项目路径: {PROJECT_ROOT}")
    logger.info("=" * 50)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
