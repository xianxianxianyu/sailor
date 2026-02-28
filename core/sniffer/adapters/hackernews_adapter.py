from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import quote_plus

from core.models import SniffQuery, SniffResult

logger = logging.getLogger("sailor")

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsAdapter:
    channel_id = "hackernews"
    display_name = "Hacker News"
    icon = "🟠"
    tier = "free"
    media_types = ["article", "discussion"]

    def check(self) -> dict:
        try:
            req = Request(f"{ALGOLIA_SEARCH_URL}?query=test&hitsPerPage=1", method="GET")
            req.add_header("User-Agent", "Sailor/1.0")
            with urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return {"status": "ok", "message": "Algolia API reachable"}
        except Exception as exc:
            return {"status": "off", "message": str(exc)}
        return {"status": "warn", "message": "Unexpected response"}

    def search(self, query: SniffQuery) -> list[SniffResult]:
        limit = min(query.max_results_per_channel, 30)
        params = f"query={quote_plus(query.keyword)}&hitsPerPage={limit}"

        time_map = {"24h": "last_24h", "7d": "last_7d", "30d": "last_30d"}
        if query.time_range in time_map:
            params += f"&tags=story&numericFilters=created_at_i>{_time_threshold(query.time_range)}"

        if query.sort_by == "time":
            url = f"https://hn.algolia.com/api/v1/search_by_date?{params}"
        else:
            url = f"{ALGOLIA_SEARCH_URL}?{params}"

        req = Request(url, method="GET")
        req.add_header("User-Agent", "Sailor/1.0")
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            logger.warning(f"[sniffer:hackernews] request failed: {exc}")
            return []

        results: list[SniffResult] = []
        for hit in data.get("hits", []):
            pub = None
            if hit.get("created_at"):
                try:
                    pub = datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
                except Exception:
                    pass

            results.append(SniffResult(
                result_id=f"hn_{hit.get('objectID', uuid.uuid4().hex)}",
                channel="hackernews",
                title=hit.get("title") or hit.get("story_title") or "",
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                snippet=_build_snippet(hit),
                author=hit.get("author"),
                published_at=pub,
                media_type="discussion" if not hit.get("url") else "article",
                metrics={
                    "likes": hit.get("points", 0),
                    "comments": hit.get("num_comments", 0),
                },
                raw_data=hit,
                query_keyword=query.keyword,
            ))
        return results


def _build_snippet(hit: dict) -> str:
    if hit.get("_highlightResult", {}).get("title", {}).get("value"):
        return hit["_highlightResult"]["title"]["value"]
    return hit.get("title") or ""


def _time_threshold(time_range: str) -> int:
    import time
    now = int(time.time())
    deltas = {"24h": 86400, "7d": 604800, "30d": 2592000}
    return now - deltas.get(time_range, 0)
