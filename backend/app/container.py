from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.collector import CollectionEngine, MinifluxCollector, RSSCollector
from core.pipeline import build_default_pipeline
from core.services import IngestionService
from core.storage import Database, KnowledgeBaseRepository, ResourceRepository
from core.tasks import MainUserFlowTaskPlanner

from .config import Settings, load_settings


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    db: Database
    resource_repo: ResourceRepository
    kb_repo: KnowledgeBaseRepository
    ingestion_service: IngestionService
    task_planner: MainUserFlowTaskPlanner


def build_container(project_root: Path) -> AppContainer:
    settings = load_settings(project_root)
    db = Database(settings.db_path)
    db.init_schema()

    resource_repo = ResourceRepository(db)
    kb_repo = KnowledgeBaseRepository(db)
    kb_repo.ensure_defaults()

    collectors = [
        RSSCollector(seed_file=settings.seed_file, source_name="rss"),
        MinifluxCollector(
            base_url=settings.miniflux_base_url,
            token=settings.miniflux_token,
            source_name="rsshub",
        ),
    ]
    ingestion_service = IngestionService(
        engine=CollectionEngine(collectors=collectors),
        pipeline=build_default_pipeline(),
        resource_repo=resource_repo,
    )
    task_planner = MainUserFlowTaskPlanner(resource_repo)

    return AppContainer(
        settings=settings,
        db=db,
        resource_repo=resource_repo,
        kb_repo=kb_repo,
        ingestion_service=ingestion_service,
        task_planner=task_planner,
    )
