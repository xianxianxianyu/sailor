from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from core.models import CompareSummary, SniffResult


_COMPARE_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "sniffer-compare-summary.md"


class SummaryEngine:
    """Generate search summary from results using pure rules (no LLM)."""

    def __init__(self, sniffer_repo=None) -> None:
        self._repo = sniffer_repo

    def summarize(self, results: list[SniffResult], keyword: str) -> dict:
        if not results:
            return {
                "total": 0,
                "keyword": keyword,
                "channel_distribution": {},
                "keyword_clusters": [],
                "time_distribution": {},
                "top_by_engagement": [],
            }

        # Check cache
        cache_key = self._cache_key(keyword, results)
        if self._repo:
            cached = self._repo.get_cached_summary(cache_key)
            if cached:
                return json.loads(cached)

        # Channel distribution
        channel_counts: Counter[str] = Counter()
        for r in results:
            channel_counts[r.channel] += 1

        # Keyword clustering
        word_counter: Counter[str] = Counter()
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on",
                      "at", "to", "for", "of", "and", "or", "with", "by", "from",
                      "that", "this", "it", "as", "be", "has", "have", "had",
                      "not", "but", "what", "how", "why", "when", "where", "who",
                      "的", "了", "在", "是", "和", "与", "或", "也", "都", "就",
                      "被", "把", "让", "给", "从", "到", "对", "中", "上", "下"}
        for r in results:
            words = re.findall(r"[\w\u4e00-\u9fff]{2,}", r.title.lower())
            for w in words:
                if w not in stop_words and w.lower() != keyword.lower():
                    word_counter[w] += 1
        keyword_clusters = [{"word": w, "count": c} for w, c in word_counter.most_common(10)]

        # Time distribution
        time_dist: Counter[str] = Counter()
        for r in results:
            if r.published_at:
                day = r.published_at.strftime("%Y-%m-%d")
                time_dist[day] += 1
            else:
                time_dist["unknown"] += 1

        # Top by engagement
        def engagement(r: SniffResult) -> int:
            m = r.metrics
            return (m.get("likes", 0) or 0) + (m.get("comments", 0) or 0) + (m.get("stars", 0) or 0)

        sorted_results = sorted(results, key=engagement, reverse=True)
        top = []
        for r in sorted_results[:5]:
            top.append({
                "result_id": r.result_id,
                "title": r.title,
                "channel": r.channel,
                "engagement": engagement(r),
            })

        summary = {
            "total": len(results),
            "keyword": keyword,
            "channel_distribution": dict(channel_counts),
            "keyword_clusters": keyword_clusters,
            "time_distribution": dict(sorted(time_dist.items())),
            "top_by_engagement": top,
        }

        # Write cache
        if self._repo:
            self._repo.set_cached_summary(cache_key, json.dumps(summary, ensure_ascii=False))

        return summary

    def compare(self, results: list[SniffResult], llm_client) -> CompareSummary:
        """LLM-powered comparison of multiple sniff results."""
        system_prompt = _COMPARE_PROMPT_PATH.read_text(encoding="utf-8")

        items_text = "\n\n".join(
            f"[{i+1}] {r.title}\nURL: {r.url}\n渠道: {r.channel}\n摘要: {r.snippet or '无'}"
            for i, r in enumerate(results)
        )
        user_content = f"请对比分析以下 {len(results)} 条资源：\n\n{items_text}"

        resp = llm_client.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
            max_tokens=2000,
        )
        parsed = _parse_json(resp.content)
        return CompareSummary(
            dimensions=parsed.get("dimensions", []),
            verdict=parsed.get("verdict", ""),
            model=resp.model,
        )

    @staticmethod
    def _cache_key(keyword: str, results: list[SniffResult]) -> str:
        ids = sorted(r.result_id for r in results)
        raw = f"{keyword}:{'|'.join(ids)}"
        return hashlib.md5(raw.encode()).hexdigest()


def _parse_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
