"""Paper Engine API Schemas"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ========== Module 1: Paper Source CRUD ==========

class PaperSourceOut(BaseModel):
    """Paper source 输出"""
    source_id: str
    platform: str
    endpoint: str
    name: str
    config: dict[str, Any]
    cursor: dict[str, Any] | None
    enabled: bool
    schedule_minutes: int | None
    last_run_at: datetime | None
    error_count: int
    last_error: str | None
    created_at: datetime | None
    updated_at: datetime | None


class CreatePaperSourceIn(BaseModel):
    """创建 paper source 输入"""
    source_id: str | None = None
    platform: str
    endpoint: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    cursor: dict[str, Any] | None = None
    enabled: bool = True
    schedule_minutes: int | None = None


class UpdatePaperSourceIn(BaseModel):
    """更新 paper source 输入"""
    name: str | None = None
    config: dict[str, Any] | None = None
    cursor: dict[str, Any] | None = None
    enabled: bool | None = None
    schedule_minutes: int | None = None


# ========== Module 2: Paper Read ==========

class PaperOut(BaseModel):
    """Paper 输出"""
    paper_id: str
    canonical_id: str
    canonical_url: str | None
    title: str
    abstract: str | None
    published_at: datetime | None
    authors: list[str] | None
    venue: str | None
    doi: str | None
    pdf_url: str | None
    external_ids: dict[str, Any] | None
    created_at: datetime | None
    updated_at: datetime | None


# ========== Module 4: Paper Runs ==========

class PaperRunOut(BaseModel):
    """Paper run 输出"""
    run_id: str
    source_id: str
    job_id: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    fetched_count: int
    processed_count: int
    error_message: str | None
    metrics: dict[str, Any] | None
    cursor_before: dict[str, Any] | None
    cursor_after: dict[str, Any] | None


# ========== Module 5: Trigger Sync ==========

class RunPaperSourceOut(BaseModel):
    """触发同步输出"""
    job_id: str
    run_id: str
    source_id: str
    status: str
    error_message: str | None = None


# ========== Research Programs ==========

class ResearchProgramOut(BaseModel):
    """Research program output"""
    program_id: str
    name: str
    description: str | None
    source_ids: list[str]
    filters: dict[str, Any]
    enabled: bool
    last_run_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class CreateResearchProgramIn(BaseModel):
    """Create research program input"""
    name: str
    description: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class UpdateResearchProgramIn(BaseModel):
    """Update research program input"""
    name: str | None = None
    description: str | None = None
    source_ids: list[str] | None = None
    filters: dict[str, Any] | None = None
    enabled: bool | None = None
