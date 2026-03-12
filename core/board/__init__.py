"""BoardEngine 模块

Board 数据模型与 Repository
"""
from core.board.adapters import BoardAdapter, GitHubTrendingAdapter, HuggingFaceAdapter
from core.board.engine import BoardRunEngine
from core.board.handlers import BoardRunHandler, BoardSnapshotHandler
from core.board.models import Board, BoardSnapshot, BoardSnapshotItem
from core.board.repository import BoardRepository
from core.board.tools import boards_capture_github, boards_capture_huggingface, boards_snapshot_ingest

__all__ = [
    "Board",
    "BoardSnapshot",
    "BoardSnapshotItem",
    "BoardRepository",
    "BoardAdapter",
    "GitHubTrendingAdapter",
    "HuggingFaceAdapter",
    "BoardSnapshotHandler",
    "BoardRunEngine",
    "BoardRunHandler",
    "boards_capture_github",
    "boards_capture_huggingface",
    "boards_snapshot_ingest",
]
