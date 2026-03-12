"""BoardEngine API Schemas"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ========== Board CRUD ==========

class BoardOut(BaseModel):
    """Board 输出"""
    board_id: str
    provider: str
    kind: str
    name: str
    config: dict[str, Any]
    enabled: bool
    last_run_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class CreateBoardIn(BaseModel):
    """创建 board 输入"""
    provider: str
    kind: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class UpdateBoardIn(BaseModel):
    """更新 board 输入"""
    name: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None


# ========== Snapshots ==========

class BoardSnapshotOut(BaseModel):
    """快照输出"""
    snapshot_id: str
    board_id: str
    window_since: str | None
    window_until: str | None
    captured_at: datetime
    raw_capture_ref: str | None
    adapter_version: str | None
    created_at: datetime | None


class BoardSnapshotItemOut(BaseModel):
    """快照条目输出"""
    snapshot_id: str
    item_key: str
    source_order: int
    title: str
    url: str
    meta: dict[str, Any] | None


# ========== Snapshot Job ==========

class SnapshotJobOut(BaseModel):
    """快照任务输出"""
    job_id: str
    snapshot_id: str | None
    status: str  # "succeeded" | "failed" | "running"
    error_message: str | None = None


# ========== Board Run ==========

class TriggerBoardRunIn(BaseModel):
    """Trigger board run input"""
    snapshot_id: str = Field(..., description="Current snapshot ID")
    baseline_snapshot_id: str | None = Field(None, description="Baseline snapshot ID (optional)")


class BoardRunJobOut(BaseModel):
    """Board run job output"""
    job_id: str
    bundle_id: str | None = None
    artifact_id: str | None = None
    status: str  # "succeeded" | "failed" | "running"
    error_message: str | None = None
    new_count: int | None = None
    removed_count: int | None = None
    kept_count: int | None = None
