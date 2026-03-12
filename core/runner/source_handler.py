"""SourceHandler — JobHandler implementation for source collection runs."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from core.models import Job
from core.pipeline.base import PreprocessPipeline
from core.sources.collectors import collect_source_entries
from core.storage.repositories import ResourceRepository
from core.storage.source_repository import SourceRepository
from .handlers import JobCancelled, RunContext

logger = logging.getLogger(__name__)


class SourceHandler:
    """Executes a source collection run inside the JobRunner lifecycle."""

    def __init__(
        self,
        source_repo: SourceRepository,
        resource_repo: ResourceRepository,
        pipeline: PreprocessPipeline,
        base_dir: Path,
    ) -> None:
        self.source_repo = source_repo
        self.resource_repo = resource_repo
        self.pipeline = pipeline
        self.base_dir = base_dir

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json)
        source_id: str = input_data["source_id"]

        source = self.source_repo.get_source(source_id)
        if not source:
            raise ValueError(f"Source not found: {source_id}")

        # Dual-write: keep SourceRunLog for backward compat
        run = self.source_repo.create_run(source_id)

        ctx.emit_event(
            "SourceCollectStarted",
            payload={"source_id": source_id, "source_type": source.source_type},
            entity_refs={"source_id": source_id},
        )

        entries = []
        processed = 0
        try:
            ctx.raise_if_cancel_requested("Source run cancelled before collection")
            entries = collect_source_entries(source, self.base_dir)

            for entry in entries:
                ctx.raise_if_cancel_requested("Source run cancelled by user")
                resource = self.pipeline.process(entry)
                self.resource_repo.upsert(resource)
                self.source_repo.upsert_item_index(
                    source_id=source.source_id,
                    item_key=entry.entry_id,
                    canonical_url=resource.canonical_url,
                    resource_id=resource.resource_id,
                )
                processed += 1

            self.source_repo.finish_run(
                run.run_id,
                status="success",
                fetched_count=len(entries),
                processed_count=processed,
                metadata={"source_type": source.source_type},
            )

            ctx.emit_event(
                "SourceCollectFinished",
                payload={"fetched": len(entries), "processed": processed},
                entity_refs={"source_id": source_id, "source_run_id": run.run_id},
            )

            return json.dumps({
                "source_run_id": run.run_id,
                "fetched_count": len(entries),
                "processed_count": processed,
            })

        except JobCancelled as exc:
            self.source_repo.finish_run(
                run.run_id,
                status="cancelled",
                fetched_count=len(entries),
                processed_count=processed,
                error_message=str(exc)[:500],
                metadata={"source_type": source.source_type},
            )
            ctx.emit_event(
                "SourceCollectCancelled",
                payload={"fetched": len(entries), "processed": processed, "reason": str(exc)[:500]},
                entity_refs={"source_id": source_id, "source_run_id": run.run_id},
            )
            raise
        except Exception as exc:
            self.source_repo.finish_run(
                run.run_id,
                status="failed",
                fetched_count=len(entries),
                processed_count=processed,
                error_message=str(exc)[:500],
                metadata={"source_type": source.source_type},
            )
            raise
