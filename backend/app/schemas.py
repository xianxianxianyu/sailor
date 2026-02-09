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
