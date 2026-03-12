from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from core.agent.article_agent import ArticleAnalysisAgent
from core.agent.base import LLMClient
from core.agent.kb_agent import KBClusterAgent
from core.agent.tagging_agent import TaggingAgent
from core.artifact.repository import ArtifactRepository
from core.board import BoardRepository
from core.follow import FollowRepository
from core.paper import PaperRepository, PaperSourceHandler
from core.pipeline import build_default_pipeline
from core.runner import JobRunner, PolicyGate, SnifferHandler, SourceHandler, TaggingHandler, IntelligenceHandler, UnifiedScheduler
from core.storage import (
    AnalysisRepository,
    Database,
    JobRepository,
    KBGraphRepository,
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
    analysis_repo: AnalysisRepository
    report_repo: KBReportRepository
    tag_repo: TagRepository
    source_repo: SourceRepository
    paper_repo: PaperRepository
    board_repo: BoardRepository
    follow_repo: FollowRepository
    artifact_repo: ArtifactRepository
    kb_graph_repo: KBGraphRepository
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
    llm_config_engine: "LLMConfigEngine"
    kg_link_engine: "KGLinkEngine"
    intelligence_engine: "ResourceIntelligenceEngine"


def build_container(project_root: Path) -> AppContainer:
    settings = load_settings(project_root)
    db = Database(settings.db_path)
    db.init_schema()

    resource_repo = ResourceRepository(db)
    kb_repo = KnowledgeBaseRepository(db)
    kb_repo.ensure_defaults()
    analysis_repo = AnalysisRepository(db)
    report_repo = KBReportRepository(db)
    tag_repo = TagRepository(db)
    source_repo = SourceRepository(db)
    paper_repo = PaperRepository(db)
    board_repo = BoardRepository(db)
    follow_repo = FollowRepository(db)
    artifact_repo = ArtifactRepository(db)
    kb_graph_repo = KBGraphRepository(db)

    task_planner = MainUserFlowTaskPlanner(resource_repo)

    # LLM Config Engine
    from core.llm_config.engine import LLMConfigEngine
    data_dir = settings.db_path.parent
    config_path = data_dir / "llm_config.json"
    llm_config_engine = LLMConfigEngine(config_path)

    # Create LLM client with Engine reference
    llm_client = llm_config_engine.create_llm_client()
    llm_client._engine = llm_config_engine  # 注入 Engine 引用，启用新调用路径

    # Create agents
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
    job_runner = JobRunner(job_repo, policy_gate=policy_gate, data_dir=data_dir)
    pipeline = build_default_pipeline()
    source_handler = SourceHandler(
        source_repo=source_repo,
        resource_repo=resource_repo,
        pipeline=pipeline,
        base_dir=settings.opml_file.parent,
    )
    job_runner.register("source_run", source_handler)

    # Paper source handler
    from core.paper_logic import PaperSyncDispatcher

    paper_sync_port = PaperSyncDispatcher()
    paper_handler = PaperSourceHandler(paper_repo, paper_sync_port)
    job_runner.register("paper_source_run", paper_handler)

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

    # App heavy endpoints (P0-3): jobify router sync work
    from core.runner.app_job_handlers import (
        AnalysisRunHandler,
        KBReportsGenerateHandler,
        ResourceAnalyzeHandler,
        SnifferCompareHandler,
        SnifferConvertSourceHandler,
        SnifferDeepAnalyzeHandler,
        SnifferSaveToKBHandler,
        SourceCatalogUpsertHandler,
        SourceDeleteHandler,
        SourceImportFeedsHandler,
    )

    job_runner.register(
        "resource_analyze",
        ResourceAnalyzeHandler(
            resource_repo=resource_repo,
            analysis_repo=analysis_repo,
            article_agent=article_agent,
        ),
    )
    job_runner.register("upsert_source", SourceCatalogUpsertHandler(source_repo))
    job_runner.register("import_feeds", SourceImportFeedsHandler(source_repo))
    job_runner.register("delete_source", SourceDeleteHandler(source_repo))
    job_runner.register("analysis_run", AnalysisRunHandler(article_agent=article_agent))
    job_runner.register(
        "kb_reports_generate",
        KBReportsGenerateHandler(kb_agent=kb_agent),
    )
    job_runner.register(
        "sniffer_deep_analyze",
        SnifferDeepAnalyzeHandler(
            sniffer_repo=sniffer_repo,
            resource_repo=resource_repo,
            article_agent=article_agent,
        ),
    )
    job_runner.register(
        "sniffer_compare",
        SnifferCompareHandler(
            sniffer_repo=sniffer_repo,
            summary_engine=summary_engine,
            llm_client=llm_client,
        ),
    )
    job_runner.register(
        "sniffer_save_to_kb",
        SnifferSaveToKBHandler(
            sniffer_repo=sniffer_repo,
            resource_repo=resource_repo,
            kb_repo=kb_repo,
        ),
    )
    job_runner.register(
        "sniffer_convert_source",
        SnifferConvertSourceHandler(
            sniffer_repo=sniffer_repo,
            source_repo=source_repo,
        ),
    )

    # Board snapshot handler
    from core.board.handlers import BoardSnapshotHandler
    board_snapshot_handler = BoardSnapshotHandler(board_repo)
    job_runner.register("board_snapshot", board_snapshot_handler)

    # Board run handler
    from core.board.engine import BoardRunEngine
    from core.board.handlers import BoardRunHandler
    board_run_engine = BoardRunEngine(board_repo)
    board_run_handler = BoardRunHandler(board_repo, artifact_repo, board_run_engine)
    job_runner.register("board_run", board_run_handler)

    # Research snapshot handler
    from core.paper.handlers import ResearchSnapshotHandler
    research_snapshot_handler = ResearchSnapshotHandler(paper_repo)
    job_runner.register("research_snapshot", research_snapshot_handler)

    # Research run handler
    from core.paper.engine import ResearchRunEngine
    from core.paper.handlers import ResearchRunHandler
    research_run_engine = ResearchRunEngine(paper_repo)
    research_run_handler = ResearchRunHandler(paper_repo, artifact_repo, research_run_engine)
    job_runner.register("research_run", research_run_handler)

    # Issue compose handler
    from core.follow.composer import IssueComposerEngine
    from core.follow.handlers import IssueComposeHandler
    issue_composer_engine = IssueComposerEngine()
    issue_compose_handler = IssueComposeHandler(artifact_repo, issue_composer_engine)
    job_runner.register("issue_compose", issue_compose_handler)

    # Follow orchestrator
    from core.follow.orchestrator import FollowOrchestrator
    follow_orchestrator = FollowOrchestrator(
        follow_repo=follow_repo,
        board_repo=board_repo,
        paper_repo=paper_repo,
        artifact_repo=artifact_repo,
        job_repo=job_repo,
        job_runner=job_runner,
    )

    # Follow run handler
    from core.follow.run_handler import FollowRunHandler
    follow_run_handler = FollowRunHandler(follow_orchestrator, follow_repo)
    job_runner.register("follow_run", follow_run_handler)

    # KG handlers (P1: auto-linking)
    from core.kg import KGLinkEngine, KGAddNodeHandler, KGRelinkNodeHandler
    kg_link_engine = KGLinkEngine(llm=llm_client)
    kg_add_node_handler = KGAddNodeHandler(kg_repo=kb_graph_repo, link_engine=kg_link_engine)
    kg_relink_node_handler = KGRelinkNodeHandler(kg_repo=kb_graph_repo, link_engine=kg_link_engine)
    job_runner.register("kg_add_node", kg_add_node_handler)
    job_runner.register("kg_relink_node", kg_relink_node_handler)

    # Unified Scheduler (replaces SnifferScheduler)
    scheduler = UnifiedScheduler(
        job_repo=job_repo,
        job_runner=job_runner,
        sniffer_repo=sniffer_repo,
        source_repo=source_repo,
        follow_repo=follow_repo,
    )
    scheduler.start()

    container = AppContainer(
        settings=settings,
        db=db,
        resource_repo=resource_repo,
        kb_repo=kb_repo,
        analysis_repo=analysis_repo,
        report_repo=report_repo,
        tag_repo=tag_repo,
        source_repo=source_repo,
        paper_repo=paper_repo,
        board_repo=board_repo,
        follow_repo=follow_repo,
        artifact_repo=artifact_repo,
        kb_graph_repo=kb_graph_repo,
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
        llm_config_engine=llm_config_engine,
        kg_link_engine=kg_link_engine,
        intelligence_engine=intelligence_engine,
    )

    # Set container reference for hot reload
    llm_config_engine.set_container(container)

    return container
