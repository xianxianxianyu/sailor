"""Paper Engine Models

Paper Engine 数据层模型定义（模块 1-4）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class PaperSource:
    """Paper 采集源（模块 1）"""
    source_id: str
    platform: str  # arxiv / openreview
    endpoint: str  # query / venue_id
    name: str
    config_json: str  # JSON string
    cursor_json: str | None = None
    enabled: bool = True
    schedule_minutes: int | None = None
    last_run_at: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Paper:
    """Paper canonical 容器（模块 2）"""
    paper_id: str
    canonical_id: str
    canonical_url: str | None
    title: str
    abstract: str | None = None
    published_at: datetime | None = None
    authors_json: str | None = None  # JSON array
    venue: str | None = None
    doi: str | None = None
    pdf_url: str | None = None
    external_ids_json: str | None = None  # JSON
    raw_meta_json: str | None = None  # JSON
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class PaperSourceItem:
    """Paper source item 索引（模块 3）"""
    source_id: str
    item_key: str
    paper_id: str
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(slots=True)
class PaperRun:
    """Paper run 记录（模块 4）"""
    run_id: str
    source_id: str
    job_id: str | None
    status: str  # running / succeeded / failed
    started_at: datetime
    finished_at: datetime | None = None
    fetched_count: int = 0
    processed_count: int = 0
    error_message: str | None = None
    metrics_json: str | None = None  # JSON
    cursor_before_json: str | None = None
    cursor_after_json: str | None = None


# Logic layer port structures (for module 5)

@dataclass(slots=True)
class PaperRecord:
    """逻辑层产出的 paper 归一化结果"""
    canonical_id: str
    canonical_url: str | None
    title: str
    item_key: str  # for paper_source_items
    abstract: str | None = None
    published_at: datetime | None = None
    authors: list[str] | None = None
    venue: str | None = None
    doi: str | None = None
    pdf_url: str | None = None
    external_ids: dict | None = None
    raw_meta: dict | None = None


@dataclass(slots=True)
class PaperSyncResult:
    """逻辑层同步结果"""
    papers: list[PaperRecord]
    next_cursor_json: dict | None = None
    metrics_json: dict | None = None


# Research snapshot models (P2.1)

@dataclass(slots=True)
class ResearchProgram:
    """Research program configuration (similar to Board)

    Defines a research topic/query with paper source filters.
    """
    program_id: str
    name: str
    description: str | None
    source_ids: str  # JSON array of paper_source IDs
    filters_json: str  # JSON: {"categories": [...], "keywords": [...], "venues": [...]}
    enabled: bool = True
    last_run_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class ResearchSnapshot:
    """Research snapshot (immutable point-in-time capture)

    Similar to BoardSnapshot but for papers.
    """
    snapshot_id: str
    program_id: str
    window_since: str | None  # ISO datetime string
    window_until: str | None  # ISO datetime string
    captured_at: datetime
    paper_count: int  # Denormalized count for quick access
    created_at: datetime | None = None


@dataclass(slots=True)
class ResearchSnapshotItem:
    """Research snapshot item (links papers to snapshots)

    Similar to BoardSnapshotItem.
    """
    snapshot_id: str
    paper_id: str  # FK to papers.paper_id
    source_order: int  # Order from source (e.g., by published_at DESC)


def paper_to_research_item(paper: Paper) -> dict:
    """Convert Paper object to ResearchBundle item format

    Args:
        paper: Paper object to convert

    Returns:
        Dict in ResearchBundle item format with fields:
        - item_key: canonical_id as stable reference
        - title: paper title
        - url: canonical_url
        - published_at: ISO format datetime string
        - summary: truncated abstract (200 chars)
        - authors: list of author names
        - venue: publication venue
        - meta: dict with doi, pdf_url, external_ids
    """
    import json

    # Parse JSON fields with error handling
    authors = None
    if paper.authors_json:
        try:
            authors = json.loads(paper.authors_json)
        except (json.JSONDecodeError, TypeError):
            authors = None

    external_ids = None
    if paper.external_ids_json:
        try:
            external_ids = json.loads(paper.external_ids_json)
        except (json.JSONDecodeError, TypeError):
            external_ids = None

    # Truncate abstract to 200 chars for summary
    summary = None
    if paper.abstract:
        if len(paper.abstract) > 200:
            summary = paper.abstract[:197] + "..."
        else:
            summary = paper.abstract

    return {
        "item_key": paper.canonical_id,
        "title": paper.title,
        "url": paper.canonical_url,
        "published_at": paper.published_at.isoformat() if paper.published_at else None,
        "summary": summary,
        "authors": authors,
        "venue": paper.venue,
        "meta": {
            "doi": paper.doi,
            "pdf_url": paper.pdf_url,
            "external_ids": external_ids,
        }
    }
