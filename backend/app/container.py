from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.agent.article_agent import ArticleAnalysisAgent
from core.agent.base import LLMClient, LLMConfig
from core.agent.kb_agent import KBClusterAgent
from core.agent.tagging_agent import TaggingAgent
from core.collector import CollectionEngine, LiveRSSCollector, MinifluxCollector, RSSCollector
from core.pipeline import build_default_pipeline
from core.services import IngestionService
from core.storage import (
    AnalysisRepository,
    Database,
    FeedRepository,
    KBReportRepository,
    KnowledgeBaseRepository,
    ResourceRepository,
    TagRepository,
)
from core.tasks import MainUserFlowTaskPlanner

from .config import Settings, load_settings


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    db: Database
    resource_repo: ResourceRepository
    kb_repo: KnowledgeBaseRepository
    feed_repo: FeedRepository
    analysis_repo: AnalysisRepository
    report_repo: KBReportRepository
    tag_repo: TagRepository
    ingestion_service: IngestionService
    task_planner: MainUserFlowTaskPlanner
    llm_client: LLMClient
    article_agent: ArticleAnalysisAgent
    kb_agent: KBClusterAgent
    tagging_agent: TaggingAgent


def build_container(project_root: Path) -> AppContainer:
    settings = load_settings(project_root)
    db = Database(settings.db_path)
    db.init_schema()

    resource_repo = ResourceRepository(db)
    kb_repo = KnowledgeBaseRepository(db)
    kb_repo.ensure_defaults()
    feed_repo = FeedRepository(db)
    analysis_repo = AnalysisRepository(db)
    report_repo = KBReportRepository(db)
    tag_repo = TagRepository(db)

    collectors = [
        RSSCollector(seed_file=settings.seed_file, source_name="rss"),
        MinifluxCollector(
            base_url=settings.miniflux_base_url,
            token=settings.miniflux_token,
            source_name="rsshub",
        ),
        LiveRSSCollector(feed_repo=feed_repo, source_name="live_rss"),
    ]
    ingestion_service = IngestionService(
        engine=CollectionEngine(collectors=collectors),
        pipeline=build_default_pipeline(),
        resource_repo=resource_repo,
    )
    task_planner = MainUserFlowTaskPlanner(resource_repo)

    llm_config = LLMConfig(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
    )
    llm_client = LLMClient(llm_config)
    article_agent = ArticleAnalysisAgent(
        llm=llm_client,
        analysis_repo=analysis_repo,
        resource_repo=resource_repo,
        kb_repo=kb_repo,
    )
    kb_agent = KBClusterAgent(
        llm=llm_client,
        report_repo=report_repo,
        analysis_repo=analysis_repo,
        resource_repo=resource_repo,
        kb_repo=kb_repo,
    )
    tagging_agent = TaggingAgent(llm=llm_client, tag_repo=tag_repo)

    return AppContainer(
        settings=settings,
        db=db,
        resource_repo=resource_repo,
        kb_repo=kb_repo,
        feed_repo=feed_repo,
        analysis_repo=analysis_repo,
        report_repo=report_repo,
        tag_repo=tag_repo,
        ingestion_service=ingestion_service,
        task_planner=task_planner,
        llm_client=llm_client,
        article_agent=article_agent,
        kb_agent=kb_agent,
        tagging_agent=tagging_agent,
    )
