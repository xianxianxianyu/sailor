"""BoardEngine 数据模型

BoardEngine 数据层模型定义
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Board:
    """Board 配置（SSOT）"""
    board_id: str
    provider: str  # github / huggingface / custom
    kind: str  # repos / models / spaces / papers / collections
    name: str
    config_json: str  # JSON string
    enabled: bool = True
    last_run_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class BoardSnapshot:
    """Board 快照（不可变）"""
    snapshot_id: str
    board_id: str
    window_since: str | None  # ISO datetime string
    window_until: str | None  # ISO datetime string
    captured_at: datetime
    raw_capture_ref: str | None  # 指向 raw_captures 或文件
    adapter_version: str | None
    created_at: datetime | None = None


@dataclass(slots=True)
class BoardSnapshotItem:
    """Board 快照条目"""
    snapshot_id: str
    item_key: str  # 稳定、版本化（如 v1:github_repo:owner/name）
    source_order: int  # 来源顺序
    title: str
    url: str
    meta_json: str | None = None  # JSON string（stars/likes/author/tags 等）
