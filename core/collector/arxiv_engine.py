from __future__ import annotations

from datetime import datetime
from typing import Any

from core.models import RawEntry


class ArxivCollector:
    """arXiv 学术论文采集器"""

    def __init__(self, config: dict[str, Any]):
        self.query = config.get("query", "all:AI")
        self.max_results = config.get("max_results", 20)
        self.categories = config.get("categories", [])  # 如 ["cs.AI", "cs.LG"]

    def collect(self) -> list[RawEntry]:
        import arxiv

        query = self._build_query()
        client = arxiv.Client(page_size=self.max_results, delay_seconds=3)

        search = arxiv.Search(
            query=query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        entries: list[RawEntry] = []
        for result in client.results(search):
            entry = RawEntry(
                entry_id=result.entry_id,
                feed_id="arxiv",
                source="arxiv",
                title=result.title,
                url=result.entry_id,
                content=result.summary,
                published_at=result.published,
            )
            entries.append(entry)
        return entries

    def _build_query(self) -> str:
        """构建 arXiv 查询语句"""
        parts = []
        if self.query:
            parts.append(self.query)
        if self.categories:
            cat_query = " OR ".join(f"cat:{c}" for c in self.categories)
            parts.append(f"({cat_query})")
        return " AND ".join(parts) if parts else "all:AI"