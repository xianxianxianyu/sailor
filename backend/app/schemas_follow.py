"""Pydantic schemas for Follow API"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateFollowIn(BaseModel):
    """Schema for creating a Follow"""
    name: str
    description: str | None = None
    board_ids: list[str] = Field(default_factory=list)
    research_program_ids: list[str] = Field(default_factory=list)
    window_policy: str = "daily"
    schedule_minutes: int | None = None
    enabled: bool = True


class UpdateFollowIn(BaseModel):
    """Schema for updating a Follow"""
    name: str | None = None
    description: str | None = None
    board_ids: list[str] | None = None
    research_program_ids: list[str] | None = None
    window_policy: str | None = None
    schedule_minutes: int | None = None
    enabled: bool | None = None


class FollowOut(BaseModel):
    """Schema for Follow output"""
    follow_id: str
    name: str
    description: str | None
    board_ids: list[str]
    research_program_ids: list[str]
    window_policy: str
    schedule_minutes: int | None
    enabled: bool
    last_run_at: datetime | None
    error_count: int
    last_error: str | None
    created_at: datetime | None
    updated_at: datetime | None


class FollowRunJobOut(BaseModel):
    """Schema for Follow run job output"""
    job_id: str
    follow_id: str
    status: str
    error_message: str | None


class TriggerFollowRunIn(BaseModel):
    """Schema for triggering a Follow run"""
    window: dict[str, str] | None = None


class IssueSnapshotOut(BaseModel):
    """Schema for IssueSnapshot output"""
    issue_id: str
    follow_id: str
    window: dict[str, str]
    sections: list[dict]
    metadata: dict
    created_at: datetime
