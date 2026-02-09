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
