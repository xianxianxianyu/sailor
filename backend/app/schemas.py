from __future__ import annotations



from datetime import datetime

from typing import Any



from pydantic import BaseModel, Field





class ResourceOut(BaseModel):

    resource_id: str

    canonical_url: str

    source: str

    title: str

    published_at: datetime | None

    text: str

    original_url: str

    topics: list[str]

    summary: str





class KnowledgeBaseOut(BaseModel):

    kb_id: str

    name: str

    description: str | None





class AddKbItemIn(BaseModel):

    resource_id: str





class KbItemOut(BaseModel):

    kb_id: str

    resource_id: str

    added_at: datetime

    kg_job_id: str | None = None





class MainFlowTaskOut(BaseModel):

    task_id: str

    task_type: str

    title: str

    description: str

    resource_id: str

    priority: str

    status: str





class IngestionRunOut(BaseModel):

    collected_count: int

    processed_count: int





class RunBatchOut(BaseModel):

    source_type: str

    total_sources: int

    success_count: int

    failed_count: int

    total_fetched: int

    total_processed: int

    job_ids: list[str] = []

    status: str = "completed"





class SourceOut(BaseModel):

    source_id: str

    source_type: str

    name: str

    endpoint: str | None

    config: dict[str, Any]

    enabled: bool

    schedule_minutes: int

    last_run_at: datetime | None

    error_count: int

    last_error: str | None

    created_at: datetime | None

    updated_at: datetime | None





class CreateSourceIn(BaseModel):

    source_id: str | None = None

    source_type: str

    name: str

    endpoint: str | None = None

    config: dict[str, Any] = Field(default_factory=dict)

    enabled: bool = True

    schedule_minutes: int = 30





class UpdateSourceIn(BaseModel):

    name: str | None = None

    endpoint: str | None = None

    config: dict[str, Any] | None = None

    enabled: bool | None = None

    schedule_minutes: int | None = None





class ImportSourcesIn(BaseModel):

    config_file: str | None = None





class ImportSourcesOut(BaseModel):

    imported: int

    total_parsed: int





class SourceStatusOut(BaseModel):

    total: int

    enabled: int

    errored: int

    last_run_at: str | None





class SourceRunOut(BaseModel):

    run_id: str

    source_id: str

    started_at: datetime

    finished_at: datetime | None

    status: str

    fetched_count: int

    processed_count: int

    error_message: str | None

    metadata: dict[str, Any]





class RunSourceOut(BaseModel):

    job_id: str = ""

    run_id: str

    source_id: str

    status: str

    fetched_count: int

    processed_count: int

    error_message: str | None = None





class SourceResourceOut(BaseModel):

    resource_id: str

    canonical_url: str

    source: str

    title: str

    published_at: datetime | None

    text: str

    original_url: str

    topics: list[str]

    summary: str

    last_seen_at: datetime | None





# --- S2: 文章分析 ---



class ResourceAnalysisOut(BaseModel):

    resource_id: str

    summary: str

    topics: list[str]

    scores: dict

    kb_recommendations: list[dict]

    insights: dict

    model: str

    prompt_tokens: int

    completion_tokens: int

    status: str

    error_message: str | None

    created_at: datetime | None

    completed_at: datetime | None





class AnalysisStatusOut(BaseModel):

    total: int

    pending: int

    completed: int

    failed: int





class RunAnalysisIn(BaseModel):

    resource_ids: list[str] | None = None





class RunAnalysisOut(BaseModel):

    analyzed_count: int

    failed_count: int





# --- S3: KB 报告 ---



class KBReportOut(BaseModel):

    report_id: str

    kb_id: str

    report_type: str

    content: dict

    resource_count: int

    model: str

    prompt_tokens: int

    completion_tokens: int

    status: str

    error_message: str | None

    created_at: datetime | None

    completed_at: datetime | None





class GenerateReportsIn(BaseModel):

    report_types: list[str] | None = None





# --- Tag 管理 ---



class TagOut(BaseModel):

    tag_id: str

    name: str

    color: str

    weight: int

    created_at: datetime | None





class CreateTagIn(BaseModel):

    name: str

    color: str = "#0f766e"





class UpdateTagIn(BaseModel):

    name: str | None = None

    color: str | None = None





# --- LLM 设置 ---



class LLMSettingsOut(BaseModel):

    provider: str

    api_key_set: bool

    api_key_preview: str

    base_url: str

    model: str

    temperature: float

    max_tokens: int





class UpdateLLMSettingsIn(BaseModel):

    provider: str

    api_key: str | None = None

    base_url: str

    model: str

    temperature: float = 0.3

    max_tokens: int = 1500





class TestLLMOut(BaseModel):

    success: bool

    message: str





class EmbeddingSettingsOut(BaseModel):

    provider: str

    api_key_set: bool

    api_key_preview: str

    base_url: str

    model: str

    dimensions: int





class UpdateEmbeddingSettingsIn(BaseModel):

    provider: str

    api_key: str | None = None

    base_url: str

    model: str

    dimensions: int = 1536





# --- 资源嗅探 ---



class BudgetIn(BaseModel):

    max_workers: int = 5

    deadline_ms: int = 60000

    max_tool_calls: int = 20





class SniffQueryIn(BaseModel):

    keyword: str

    channels: list[str] = Field(default_factory=list)

    time_range: str = "all"

    sort_by: str = "relevance"

    max_results_per_channel: int = 10

    budget: BudgetIn | None = None





class SniffResultOut(BaseModel):

    result_id: str

    channel: str

    title: str

    url: str

    snippet: str

    author: str | None

    published_at: datetime | None

    media_type: str

    metrics: dict[str, Any]

    query_keyword: str





class SearchSummaryOut(BaseModel):

    total: int

    keyword: str

    channel_distribution: dict[str, int]

    keyword_clusters: list[dict[str, Any]]

    time_distribution: dict[str, int]

    top_by_engagement: list[dict[str, Any]]





class SearchResponseOut(BaseModel):

    job_id: str | None = None

    status: str | None = None

    error_message: str | None = None

    results: list[SniffResultOut]

    summary: SearchSummaryOut





class ChannelInfoOut(BaseModel):

    channel_id: str

    display_name: str

    icon: str

    tier: str

    media_types: list[str]

    status: str

    message: str





class SnifferPackOut(BaseModel):

    pack_id: str

    name: str

    query_json: str

    description: str | None

    created_at: datetime | None





class CreateSnifferPackIn(BaseModel):

    name: str

    query: SniffQueryIn

    description: str | None = None





# --- P1: 深度分析 / 对比 / 操作 ---



class SaveToKBIn(BaseModel):

    kb_id: str





class ConvertSourceIn(BaseModel):

    name: str | None = None

    source_type: str = "rss"





class SaveToKBOut(BaseModel):

    saved: bool

    resource_id: str

    kb_id: str





class ConvertSourceOut(BaseModel):

    converted: bool

    source_id: str





class CompareIn(BaseModel):

    result_ids: list[str]





class CompareSummaryOut(BaseModel):

    dimensions: list[dict[str, Any]]

    verdict: str

    model: str





class ImportPackIn(BaseModel):

    name: str

    query: SniffQueryIn

    description: str | None = None

    schedule_cron: str | None = None





# --- P2: 定时调度 / 健康检查 ---



class SnifferPackFullOut(BaseModel):

    pack_id: str

    name: str

    query_json: str

    description: str | None

    schedule_cron: str | None

    last_run_at: datetime | None

    next_run_at: datetime | None

    created_at: datetime | None





class UpdatePackScheduleIn(BaseModel):

    schedule_cron: str | None = None





class ChannelHealthOut(BaseModel):

    channel_id: str

    display_name: str

    icon: str

    tier: str

    status: str

    message: str

    latency_ms: int | None





# --- V2 Provenance ---



class SnifferRunOut(BaseModel):

    run_id: str

    job_id: str | None

    query_json: str

    pack_id: str | None

    status: str

    result_count: int

    channels_used: list[str]

    error_message: str | None

    started_at: datetime | None

    finished_at: datetime | None

    metadata: dict[str, Any]





class ProvenanceEventOut(BaseModel):

    event_id: str

    run_id: str

    event_type: str

    actor: str

    entity_refs: dict[str, Any]

    payload: dict[str, Any]

    ts: datetime | None





class JobOut(BaseModel):

    job_id: str

    job_type: str

    status: str

    input_json: str

    output_json: str | None

    error_class: str | None

    error_message: str | None

    created_at: datetime | None

    started_at: datetime | None

    finished_at: datetime | None

    metadata: dict[str, Any]





class JobAcceptedOut(BaseModel):

    job_id: str

    status: str

    error_message: str | None = None





class JobCancelOut(BaseModel):

    job_id: str

    status: str

    cancel_requested: bool = True





# --- Stage 4: Unified Scheduler + Confirm Gate ---



class ScheduleOut(BaseModel):

    schedule_id: str

    schedule_type: str

    ref_id: str

    interval_seconds: int

    next_run_at: datetime | None

    last_run_at: datetime | None

    enabled: bool





class PendingConfirmOut(BaseModel):

    confirm_id: str

    job_id: str | None

    action_type: str

    payload: dict

    status: str

    created_at: datetime | None

    resolved_at: datetime | None

    execution_job_id: str | None = None





class ConfirmActionIn(BaseModel):

    action: str  # "approve" | "reject"





# --- Artifacts ---



class ArtifactOut(BaseModel):

    """Artifact output"""

    artifact_id: str

    kind: str

    schema_version: str

    content: dict[str, Any]

    content_ref: str | None = None

    input_refs: dict[str, Any] | None = None

    producer: dict[str, Any] | None = None

    job_id: str | None = None

    created_at: datetime | None = None

    metadata: dict[str, Any] | None = None

