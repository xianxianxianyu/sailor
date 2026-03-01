from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from core.agent.article_agent import ArticleAnalysisAgent
from core.agent.base import LLMClient, LLMConfig
from core.agent.kb_agent import KBClusterAgent
from core.agent.tagging_agent import TaggingAgent
from core.collector import CollectionEngine, LiveRSSCollector, MinifluxCollector, RSSCollector
from core.pipeline import build_default_pipeline
from core.runner import JobRunner, PolicyGate, SnifferHandler, SourceHandler, TaggingHandler, TrendingHandler, IntelligenceHandler, IngestionHandler, UnifiedScheduler
from core.services import IngestionService
from core.storage import (
    AnalysisRepository,
    Database,
    FeedRepository,
    JobRepository,
    KBReportRepository,
    KnowledgeBaseRepository,
    ResourceRepository,
    SnifferRepository,
    SourceRepository,
    TagRepository,
)
from core.tasks import MainUserFlowTaskPlanner

from core.sniffer import ChannelRegistry, PackManager, SnifferToolModule, SummaryEngine
from core.sniffer.adapters import GitHubAdapter, HackerNewsAdapter, RSSAdapter

from .config import Settings, load_settings

logger = logging.getLogger(__name__)


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
    source_repo: SourceRepository
    ingestion_service: IngestionService
    task_planner: MainUserFlowTaskPlanner
    llm_client: LLMClient
    article_agent: ArticleAnalysisAgent
    kb_agent: KBClusterAgent
    tagging_agent: TaggingAgent
    sniffer_repo: SnifferRepository
    channel_registry: ChannelRegistry
    summary_engine: SummaryEngine
    sniffer_tool_module: SnifferToolModule
    pack_manager: PackManager
    scheduler: UnifiedScheduler | None
    job_repo: JobRepository
    job_runner: JobRunner
    policy_gate: PolicyGate | None

    def reload_llm(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        """热重载 LLM 客户端及所有依赖它的 Agent，保存设置后立即生效。"""
        new_config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        new_client = LLMClient(new_config)
        self.llm_client = new_client
        self.article_agent = ArticleAnalysisAgent(
            llm=new_client,
            analysis_repo=self.analysis_repo,
            resource_repo=self.resource_repo,
            kb_repo=self.kb_repo,
        )
        self.kb_agent = KBClusterAgent(
            llm=new_client,
            report_repo=self.report_repo,
            analysis_repo=self.analysis_repo,
            resource_repo=self.resource_repo,
            kb_repo=self.kb_repo,
        )
        self.tagging_agent = TaggingAgent(llm=new_client, tag_repo=self.tag_repo)


def _load_persisted_llm_config(data_dir: Path) -> dict:
    """读取 data/llm_config.json 中持久化的 LLM 非敏感配置。"""
    config_file = data_dir / "llm_config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("读取 llm_config.json 失败: %s", exc)
    return {}


def _load_persisted_api_key() -> str:
    """从 OS keyring 读取 API Key。"""
    try:
        import keyring
        key = keyring.get_password("sailor-llm", "api_key")
        return key or ""
    except Exception:
        return ""


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
    source_repo = SourceRepository(db)

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

    # LLM 配置优先级: keyring + llm_config.json > 环境变量
    data_dir = settings.db_path.parent
    persisted = _load_persisted_llm_config(data_dir)
    persisted_key = _load_persisted_api_key()

    llm_config = LLMConfig(
        api_key=persisted_key or settings.openai_api_key,
        base_url=persisted.get("base_url", settings.openai_base_url),
        model=persisted.get("model", settings.openai_model),
        temperature=persisted.get("temperature", 0.3),
        max_tokens=persisted.get("max_tokens", 1500),
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

    # Sniffer
    sniffer_repo = SnifferRepository(db)
    channel_registry = ChannelRegistry()
    channel_registry.register(HackerNewsAdapter())
    channel_registry.register(GitHubAdapter())
    channel_registry.register(RSSAdapter(db))
    summary_engine = SummaryEngine(sniffer_repo=sniffer_repo)
    pack_manager = PackManager(repo=sniffer_repo, registry=channel_registry)
    pack_manager.ensure_presets()

    # V2 Provenance
    job_repo = JobRepository(db)

    # PolicyGate
    policy_gate = PolicyGate(job_repo)

    # Job Runner
    job_runner = JobRunner(job_repo, policy_gate=policy_gate)
    pipeline = build_default_pipeline()
    source_handler = SourceHandler(
        source_repo=source_repo,
        resource_repo=resource_repo,
        pipeline=pipeline,
        base_dir=settings.opml_file.parent,
    )
    job_runner.register("source_run", source_handler)

    # Ingestion handler
    ingestion_handler = IngestionHandler(ingestion_service)
    job_runner.register("ingestion", ingestion_handler)

    # Sniffer handler
    sniffer_tool_module = SnifferToolModule(channel_registry, sniffer_repo)
    sniffer_handler = SnifferHandler(
        tool_module=sniffer_tool_module,
        summary_engine=summary_engine,
        job_repo=job_repo,
    )
    job_runner.register("sniffer_search", sniffer_handler)

    # Tagging handler
    tagging_handler = TaggingHandler(
        tagging_agent=tagging_agent,
        resource_repo=resource_repo,
        tag_repo=tag_repo,
    )
    job_runner.register("batch_tag", tagging_handler)

    # Trending handler
    trending_handler = TrendingHandler(
        resource_repo=resource_repo,
        tag_repo=tag_repo,
    )
    job_runner.register("trending_generate", trending_handler)

    # Intelligence engine + handler
    from core.engines.intelligence import ResourceIntelligenceEngine
    intelligence_engine = ResourceIntelligenceEngine(
        resource_repo=resource_repo,
        tag_repo=tag_repo,
        analysis_repo=analysis_repo,
        tagging_agent=tagging_agent,
        article_agent=article_agent,
    )
    intelligence_handler = IntelligenceHandler(intelligence_engine)
    job_runner.register("resource_intelligence_run", intelligence_handler)

    # Unified Scheduler (replaces SnifferScheduler)
    scheduler = UnifiedScheduler(
        job_repo=job_repo,
        job_runner=job_runner,
        sniffer_repo=sniffer_repo,
        source_repo=source_repo,
    )
    scheduler.start()

    return AppContainer(
        settings=settings,
        db=db,
        resource_repo=resource_repo,
        kb_repo=kb_repo,
        feed_repo=feed_repo,
        analysis_repo=analysis_repo,
        report_repo=report_repo,
        tag_repo=tag_repo,
        source_repo=source_repo,
        ingestion_service=ingestion_service,
        task_planner=task_planner,
        llm_client=llm_client,
        article_agent=article_agent,
        kb_agent=kb_agent,
        tagging_agent=tagging_agent,
        sniffer_repo=sniffer_repo,
        channel_registry=channel_registry,
        summary_engine=summary_engine,
        sniffer_tool_module=sniffer_tool_module,
        pack_manager=pack_manager,
        scheduler=scheduler,
        job_repo=job_repo,
        job_runner=job_runner,
        policy_gate=policy_gate,
    )

