from __future__ import annotations

import logging
from dataclasses import dataclass

from core.agent.tagging_agent import TaggingAgent
from core.storage.repositories import ResourceRepository
from core.storage.tag_repository import TagRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrendingItem:
    resource_id: str
    title: str
    original_url: str
    summary: str
    tags: list[str]
    source: str


@dataclass(slots=True)
class TrendingGroup:
    tag_name: str
    tag_color: str
    items: list[TrendingItem]


@dataclass(slots=True)
class TrendingReport:
    groups: list[TrendingGroup]
    total_resources: int
    total_tags: int


class TrendingService:
    def __init__(
        self,
        resource_repo: ResourceRepository,
        tag_repo: TagRepository,
        tagging_agent: TaggingAgent,
    ) -> None:
        self.resource_repo = resource_repo
        self.tag_repo = tag_repo
        self.tagging_agent = tagging_agent

    def generate(self, tag_resources: bool = True) -> TrendingReport:
        """生成 trending 报告：先对未打标文章打标，再按 tag 分组"""
        resources = self.resource_repo.list_resources()

        if tag_resources:
            for res in resources:
                existing = self.tag_repo.get_resource_tags(res.resource_id)
                if not existing:
                    try:
                        self.tagging_agent.tag_resource(res.resource_id, res.title, res.text)
                    except Exception:
                        logger.warning("Tagging failed for %s", res.resource_id, exc_info=True)

        # 按 tag 分组
        tags = self.tag_repo.list_tags()
        groups: list[TrendingGroup] = []

        for tag in tags:
            resource_ids = self.tag_repo.get_resources_by_tag(tag.tag_id)
            if not resource_ids:
                continue
            items = []
            for rid in resource_ids:
                res = self.resource_repo.get_resource(rid)
                if not res:
                    continue
                res_tags = self.tag_repo.get_resource_tags(rid)
                items.append(TrendingItem(
                    resource_id=res.resource_id,
                    title=res.title,
                    original_url=res.original_url,
                    summary=res.summary,
                    tags=[t.name for t in res_tags],
                    source=res.source,
                ))
            if items:
                groups.append(TrendingGroup(
                    tag_name=tag.name,
                    tag_color=tag.color,
                    items=items,
                ))

        # 按 tag weight 排序（已经是 list_tags 的排序）
        return TrendingReport(
            groups=groups,
            total_resources=len(resources),
            total_tags=len(tags),
        )
