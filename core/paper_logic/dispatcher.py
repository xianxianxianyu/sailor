"""Paper Sync Dispatcher

根据 platform 分发到对应的同步实现
"""
from __future__ import annotations

import logging

from core.paper.models import PaperSource, PaperSyncResult
from core.paper.port import PaperSyncPort

from .arxiv_sync import normalize_arxiv_atom
from .openreview_sync import normalize_openreview_notes

logger = logging.getLogger(__name__)


class PaperSyncDispatcher(PaperSyncPort):
    """Paper 同步分发器"""

    def sync(self, source: PaperSource, raw: str) -> PaperSyncResult:
        """根据 platform 分发到对应的归一化实现（无网络 I/O）"""
        logger.info("[paper-sync] 分发归一化: platform=%s, source=%s", source.platform, source.source_id)

        if source.platform == "arxiv":
            return normalize_arxiv_atom(source, raw)
        elif source.platform == "openreview":
            return normalize_openreview_notes(source, raw)
        else:
            raise ValueError(f"Unsupported platform: {source.platform}")
