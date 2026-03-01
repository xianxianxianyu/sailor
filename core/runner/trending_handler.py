"""TrendingHandler — JobHandler for generating trending reports."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict

from core.models import Job
from core.services.trending import TrendingService
from core.storage.repositories import ResourceRepository
from core.storage.tag_repository import TagRepository
from .handlers import RunContext

logger = logging.getLogger(__name__)


class TrendingHandler:
    """Generates a trending report from already-tagged resources (no collection, no tagging)."""

    def __init__(
        self,
        resource_repo: ResourceRepository,
        tag_repo: TagRepository,
    ) -> None:
        self.resource_repo = resource_repo
        self.tag_repo = tag_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        ctx.emit_event("TrendingGenerateStarted")

        # Build a TrendingService without tagging_agent — we only read existing tags
        svc = TrendingService(
            resource_repo=self.resource_repo,
            tag_repo=self.tag_repo,
            tagging_agent=None,  # type: ignore[arg-type]
        )
        report = svc.generate(tag_resources=False)

        ctx.emit_event("TrendingGenerateFinished", {
            "total_resources": report.total_resources,
            "total_tags": report.total_tags,
            "group_count": len(report.groups),
        })

        return json.dumps({
            "total_resources": report.total_resources,
            "total_tags": report.total_tags,
            "groups": [asdict(g) for g in report.groups],
        })
