"""BoardEngine Adapters

Adapters for parsing raw data from different providers into standardized BoardSnapshotItem format.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BoardAdapter(ABC):
    """Base adapter for parsing raw board data"""

    @abstractmethod
    def parse(self, raw_data: dict) -> list[dict]:
        """Parse raw data into standardized items

        Args:
            raw_data: Raw data from capture (provider-specific format)

        Returns:
            List of dicts with keys: item_key, source_order, title, url, meta (dict)
        """
        ...


class GitHubTrendingAdapter(BoardAdapter):
    """Adapter for GitHub Trending HTML scraping results"""

    def parse(self, raw_data: dict) -> list[dict]:
        """Parse GitHub Trending data

        Input format:
            {"repos": [{"owner": str, "name": str, "description": str, "stars": int, ...}]}

        Output format:
            [{"item_key": "v1:github_repo:owner/name", "source_order": int, ...}]
        """
        repos = raw_data.get("repos", [])
        items = []

        for idx, repo in enumerate(repos):
            owner = repo.get("owner", "")
            name = repo.get("name", "")
            if not owner or not name:
                continue

            full_name = f"{owner}/{name}"
            item_key = f"v1:github_repo:{full_name}"

            items.append({
                "item_key": item_key,
                "source_order": idx,
                "title": full_name,
                "url": f"https://github.com/{full_name}",
                "meta": {
                    "description": repo.get("description", ""),
                    "stars": repo.get("stars", 0),
                    "forks": repo.get("forks", 0),
                    "language": repo.get("language", ""),
                    "stars_today": repo.get("stars_today", 0),
                },
            })

        return items


class HuggingFaceAdapter(BoardAdapter):
    """Adapter for HuggingFace API results"""

    def __init__(self, kind: str = "models") -> None:
        """
        Args:
            kind: Type of HuggingFace content (models, datasets, spaces)
        """
        self.kind = kind

    def parse(self, raw_data: dict) -> list[dict]:
        """Parse HuggingFace API data

        Input format:
            {"items": [{"id": str, "author": str, "likes": int, ...}]}

        Output format:
            [{"item_key": "v1:hf_model:id", "source_order": int, ...}]
        """
        items_data = raw_data.get("items", [])
        items = []

        for idx, item in enumerate(items_data):
            item_id = item.get("id", "")
            if not item_id:
                continue

            # Determine item_key prefix based on kind
            prefix_map = {
                "models": "hf_model",
                "datasets": "hf_dataset",
                "spaces": "hf_space",
            }
            prefix = prefix_map.get(self.kind, "hf_model")
            item_key = f"v1:{prefix}:{item_id}"

            items.append({
                "item_key": item_key,
                "source_order": idx,
                "title": item_id,
                "url": f"https://huggingface.co/{item_id}",
                "meta": {
                    "author": item.get("author", ""),
                    "likes": item.get("likes", 0),
                    "downloads": item.get("downloads", 0),
                    "tags": item.get("tags", []),
                },
            })

        return items
