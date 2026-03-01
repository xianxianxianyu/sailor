"""TaggingHandler — JobHandler for batch LLM tagging of resources."""
from __future__ import annotations

import json
import logging

from core.agent.tagging_agent import TaggingAgent
from core.models import Job
from core.storage.repositories import ResourceRepository
from core.storage.tag_repository import TagRepository
from .handlers import RunContext

logger = logging.getLogger(__name__)


class TaggingHandler:
    """Executes batch tagging: tags all untagged resources via LLM."""

    def __init__(
        self,
        tagging_agent: TaggingAgent,
        resource_repo: ResourceRepository,
        tag_repo: TagRepository,
    ) -> None:
        self.tagging_agent = tagging_agent
        self.resource_repo = resource_repo
        self.tag_repo = tag_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json) if job.input_json else {}
        resource_ids: list[str] | None = input_data.get("resource_ids")

        if resource_ids:
            resources = [
                r for r in (self.resource_repo.get_resource(rid) for rid in resource_ids)
                if r is not None
            ]
        else:
            resources = self.resource_repo.list_resources()

        ctx.emit_event("BatchTagStarted", {"resource_count": len(resources)})

        tagged = 0
        skipped = 0
        failed = 0
        for res in resources:
            existing = self.tag_repo.get_resource_tags(res.resource_id)
            if existing:
                skipped += 1
                continue
            try:
                self.tagging_agent.tag_resource(res.resource_id, res.title, res.text)
                tagged += 1
            except Exception:
                logger.warning("Tagging failed for %s", res.resource_id, exc_info=True)
                failed += 1

        ctx.emit_event("BatchTagFinished", {"tagged": tagged, "skipped": skipped, "failed": failed})

        return json.dumps({"tagged": tagged, "skipped": skipped, "failed": failed})
