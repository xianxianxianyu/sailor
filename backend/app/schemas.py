from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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


class ImportOPMLIn(BaseModel):
    opml_file: str | None = None


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
