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


# --- S1: Feed 管理 ---

class FeedOut(BaseModel):
    feed_id: str
    name: str
    xml_url: str
    html_url: str | None
    enabled: bool
    last_fetched_at: datetime | None
    error_count: int
    last_error: str | None
    created_at: datetime | None


class RunFeedOut(BaseModel):
    feed_id: str
    status: str
    fetched_count: int
    processed_count: int


class RunBatchOut(BaseModel):
    source_type: str
    total_sources: int
    success_count: int
    failed_count: int
    total_fetched: int
    total_processed: int


class ImportOPMLIn(BaseModel):
    opml_file: str | None = None


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
    rss_synced: int
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
    run_id: str
    source_id: str
    status: str
    fetched_count: int
    processed_count: int


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
