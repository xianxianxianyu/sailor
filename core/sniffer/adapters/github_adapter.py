from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import quote_plus

from core.models import SniffQuery, SniffResult

logger = logging.getLogger("sailor")

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"


class GitHubAdapter:
    channel_id = "github"
    display_name = "GitHub"
    icon = "🐙"
    tier = "free"
    media_types = ["repo"]

    def check(self) -> dict:
        try:
            req = Request("https://api.github.com/rate_limit", method="GET")
            req.add_header("User-Agent", "Sailor/1.0")
            token = os.environ.get("GITHUB_TOKEN", "")
            if token:
                req.add_header("Authorization", f"token {token}")
            with urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return {"status": "ok", "message": "GitHub API reachable"}
        except Exception as exc:
            return {"status": "off", "message": str(exc)}
        return {"status": "warn", "message": "Unexpected response"}

    def search(self, query: SniffQuery) -> list[SniffResult]:
        limit = min(query.max_results_per_channel, 30)
        q = quote_plus(query.keyword)

        # Add time filter
        if query.time_range != "all":
            from datetime import timedelta
            now = datetime.utcnow()
            deltas = {"24h": timedelta(days=1), "7d": timedelta(days=7), "30d": timedelta(days=30)}
            if query.time_range in deltas:
                since = (now - deltas[query.time_range]).strftime("%Y-%m-%d")
                q += f"+pushed:>{since}"

        sort_map = {"popularity": "stars", "time": "updated", "relevance": ""}
        sort = sort_map.get(query.sort_by, "")
        url = f"{GITHUB_SEARCH_URL}?q={q}&per_page={limit}"
        if sort:
            url += f"&sort={sort}&order=desc"

        req = Request(url, method="GET")
        req.add_header("User-Agent", "Sailor/1.0")
        req.add_header("Accept", "application/vnd.github.v3+json")
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            req.add_header("Authorization", f"token {token}")

        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            logger.warning(f"[sniffer:github] request failed: {exc}")
            return []

        results: list[SniffResult] = []
        for item in data.get("items", []):
            pub = None
            if item.get("pushed_at"):
                try:
                    pub = datetime.fromisoformat(item["pushed_at"].replace("Z", "+00:00"))
                except Exception:
                    pass

            results.append(SniffResult(
                result_id=f"gh_{item.get('id', uuid.uuid4().hex)}",
                channel="github",
                title=item.get("full_name", ""),
                url=item.get("html_url", ""),
                snippet=item.get("description") or "",
                author=item.get("owner", {}).get("login"),
                published_at=pub,
                media_type="repo",
                metrics={
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "issues": item.get("open_issues_count", 0),
                },
                raw_data=item,
                query_keyword=query.keyword,
            ))
        return results
