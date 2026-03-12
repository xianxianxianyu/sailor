"""Paper Sync Port (Logic Layer Interface)

逻辑层需要实现这个接口，数据层通过它调用逻辑层的同步能力
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import PaperSource, PaperSyncResult


class PaperSyncPort(ABC):
    """逻辑层同步接口（模块 5 使用）"""

    @abstractmethod
    def sync(self, source: PaperSource, raw: str) -> PaperSyncResult:
        """
        归一化指定 paper source 的原始响应

        Args:
            source: Paper source 配置
            raw: HTTP acquisition 得到的原始响应（XML/JSON 文本）

        Returns:
            PaperSyncResult: 包含 papers/next_cursor/metrics

        Raises:
            Exception: 同步失败时抛出异常
        """
        pass
