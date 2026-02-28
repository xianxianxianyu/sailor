from __future__ import annotations

import json
import uuid

from core.models import SniffQuery, SniffResult, SnifferPack
from core.sniffer.channel_registry import ChannelRegistry
from core.storage.sniffer_repository import SnifferRepository


class PackManager:
    def __init__(self, repo: SnifferRepository, registry: ChannelRegistry) -> None:
        self.repo = repo
        self.registry = registry

    def create_pack(self, name: str, query: SniffQuery, description: str | None = None) -> SnifferPack:
        pack = SnifferPack(
            pack_id=uuid.uuid4().hex[:12],
            name=name,
            query_json=json.dumps({
                "keyword": query.keyword,
                "channels": query.channels,
                "time_range": query.time_range,
                "sort_by": query.sort_by,
                "max_results_per_channel": query.max_results_per_channel,
            }),
            description=description,
        )
        return self.repo.create_pack(pack)

    def list_packs(self) -> list[SnifferPack]:
        return self.repo.list_packs()

    def get_pack(self, pack_id: str) -> SnifferPack | None:
        return self.repo.get_pack(pack_id)

    def delete_pack(self, pack_id: str) -> bool:
        return self.repo.delete_pack(pack_id)

    def run_pack(self, pack_id: str) -> list[SniffResult]:
        pack = self.repo.get_pack(pack_id)
        if not pack:
            raise ValueError(f"Pack not found: {pack_id}")

        q_data = json.loads(pack.query_json)
        query = SniffQuery(
            keyword=q_data.get("keyword", ""),
            channels=q_data.get("channels", []),
            time_range=q_data.get("time_range", "all"),
            sort_by=q_data.get("sort_by", "relevance"),
            max_results_per_channel=q_data.get("max_results_per_channel", 10),
        )
        results = self.registry.search(query)
        self.repo.save_results(results)
        return results

    def import_pack(self, data: dict) -> SnifferPack:
        query_data = data.get("query", {})
        pack = SnifferPack(
            pack_id=uuid.uuid4().hex[:12],
            name=data.get("name", "Imported Pack"),
            query_json=json.dumps({
                "keyword": query_data.get("keyword", ""),
                "channels": query_data.get("channels", []),
                "time_range": query_data.get("time_range", "all"),
                "sort_by": query_data.get("sort_by", "relevance"),
                "max_results_per_channel": query_data.get("max_results_per_channel", 10),
            }),
            description=data.get("description"),
            schedule_cron=data.get("schedule_cron"),
        )
        return self.repo.create_pack(pack)

    def export_pack(self, pack_id: str) -> dict | None:
        pack = self.repo.get_pack(pack_id)
        if not pack:
            return None
        query_data = json.loads(pack.query_json)
        return {
            "name": pack.name,
            "description": pack.description,
            "query": query_data,
            "schedule_cron": pack.schedule_cron,
        }

    def ensure_presets(self) -> int:
        existing = {p.name for p in self.repo.list_packs()}
        presets = [
            {"name": "AI 前沿", "description": "追踪 AI/LLM/Agent 领域最新动态", "query": {"keyword": "AI LLM Agent", "channels": ["hackernews", "github"], "time_range": "week", "sort_by": "relevance", "max_results_per_channel": 10}},
            {"name": "开源热门", "description": "发现 GitHub 热门开源项目", "query": {"keyword": "open source trending", "channels": ["github"], "time_range": "week", "sort_by": "relevance", "max_results_per_channel": 15}},
            {"name": "技术博客", "description": "聚合技术博客和深度文章", "query": {"keyword": "engineering blog", "channels": ["hackernews", "rss"], "time_range": "month", "sort_by": "relevance", "max_results_per_channel": 10}},
        ]
        created = 0
        for preset in presets:
            if preset["name"] not in existing:
                self.import_pack(preset)
                created += 1
        return created