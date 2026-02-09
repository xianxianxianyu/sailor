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
