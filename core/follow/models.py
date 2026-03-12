"""Follow System Models

Full Follow model with database fields (P5.1).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class FollowSpec:
    """Follow specification (minimal for backward compatibility)

    A Follow combines research programs and boards into a unified issue.
    Used by IssueComposerEngine for backward compatibility.
    """
    follow_id: str
    name: str
    description: str | None = None
    board_ids: list[str] | None = None
    research_program_ids: list[str] | None = None
    enabled: bool = True


@dataclass(slots=True)
class Follow:
    """Full Follow specification with database fields

    A Follow is a top-level orchestration that combines:
    - Board snapshots and deltas
    - Research program snapshots
    - Issue composition

    Into a unified, scheduled workflow.
    """
    follow_id: str
    name: str
    description: str | None = None
    board_ids: list[str] | None = None  # Stored as JSON
    research_program_ids: list[str] | None = None  # Stored as JSON
    window_policy: str = "daily"  # daily|weekly|monthly|custom
    schedule_minutes: int | None = None  # Auto-run interval
    enabled: bool = True
    last_run_at: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
