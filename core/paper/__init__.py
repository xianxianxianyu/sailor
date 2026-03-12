"""Paper Engine

Paper Engine 数据层模块（模块 1-5）
"""
from .engine import ResearchRunEngine
from .handler import PaperSourceHandler
from .handlers import ResearchRunHandler, ResearchSnapshotHandler
from .models import (
    Paper,
    PaperRecord,
    PaperRun,
    PaperSource,
    PaperSourceItem,
    PaperSyncResult,
    ResearchProgram,
    ResearchSnapshot,
    ResearchSnapshotItem,
)
from .port import PaperSyncPort
from .repository import PaperRepository
from .tools import research_capture_papers, research_snapshot_ingest

__all__ = [
    "PaperRepository",
    "PaperSource",
    "Paper",
    "PaperSourceItem",
    "PaperRun",
    "PaperRecord",
    "PaperSyncResult",
    "PaperSyncPort",
    "PaperSourceHandler",
    "ResearchProgram",
    "ResearchSnapshot",
    "ResearchSnapshotItem",
    "ResearchSnapshotHandler",
    "ResearchRunEngine",
    "ResearchRunHandler",
    "research_capture_papers",
    "research_snapshot_ingest",
]
