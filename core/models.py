from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class RawEntry:
    entry_id: str
    feed_id: str
    source: str
    title: str
    url: str
    content: str
    published_at: datetime | None = None
    captured_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class Resource:
    resource_id: str
    canonical_url: str
    source: str
    provenance: dict[str, Any]
    title: str
    published_at: datetime | None
    text: str
    original_url: str
    topics: list[str]
    summary: str


@dataclass(slots=True)
class KnowledgeBase:
    kb_id: str
    name: str
    description: str | None = None


@dataclass(slots=True)
class KnowledgeBaseItem:
    kb_id: str
    resource_id: str
    added_at: datetime


@dataclass(slots=True)
class RSSFeed:
    feed_id: str
    name: str
    xml_url: str
    html_url: str | None = None
    enabled: bool = True
    last_fetched_at: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class SourceRecord:
    source_id: str
    source_type: str
    name: str
    endpoint: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    schedule_minutes: int = 30
    last_run_at: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class SourceRunLog:
    run_id: str
    source_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"
    fetched_count: int = 0
    processed_count: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceResourceRow:
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


@dataclass(slots=True)
class ResourceAnalysis:
    resource_id: str
    summary: str
    topics_json: str
    scores_json: str
    kb_recommendations_json: str
    insights_json: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    status: str = "pending"
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(slots=True)
class KBReport:
    report_id: str
    kb_id: str
    report_type: str
    content_json: str
    resource_count: int
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    status: str = "pending"
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(slots=True)
class UserTag:
    tag_id: str
    name: str
    color: str = "#0f766e"
    weight: int = 1
    created_at: datetime | None = None


@dataclass(slots=True)
class UserAction:
    id: int
    action_type: str
    resource_id: str | None = None
    tag_id: str | None = None
    kb_id: str | None = None
    metadata_json: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class ResourceTag:
    resource_id: str
    tag_id: str
    source: str = "auto"
    created_at: datetime | None = None


# --- 资源嗅探 ---


@dataclass(slots=True)
class SniffResult:
    result_id: str
    channel: str
    title: str
    url: str
    snippet: str
    author: str | None = None
    published_at: datetime | None = None
    media_type: str = "article"
    metrics: dict[str, Any] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)
    query_keyword: str = ""
    created_at: datetime | None = None


@dataclass(slots=True)
class SniffQuery:
    keyword: str
    channels: list[str] = field(default_factory=list)
    time_range: str = "all"
    sort_by: str = "relevance"
    max_results_per_channel: int = 10


@dataclass(slots=True)
class SnifferPack:
    pack_id: str
    name: str
    query_json: str = "{}"
    description: str | None = None
    schedule_cron: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class CompareSummary:
    dimensions: list[dict[str, Any]]
    verdict: str
    model: str
