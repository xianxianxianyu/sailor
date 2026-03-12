"""Research Engine Job Handlers

Job handlers for research snapshot and run operations.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from core.artifact.repository import ArtifactRepository
from core.models import Job
from core.paper.engine import ResearchRunEngine
from core.paper.repository import PaperRepository
from core.paper.tools import (
    research_capture_papers,
    research_snapshot_ingest,
)
from core.runner.handlers import RunContext

logger = logging.getLogger(__name__)


class ResearchSnapshotHandler:
    """Handler for research_snapshot jobs

    Orchestrates capture + ingest to create research snapshots.
    """

    def __init__(self, paper_repo: PaperRepository) -> None:
        self.paper_repo = paper_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        """Execute research snapshot job

        Args:
            job: Job with input_json containing program_id and optional window
            ctx: RunContext with job_repo and data_dir

        Returns:
            output_json with snapshot_id

        Raises:
            ValueError: If program not found or disabled
        """
        # Parse input
        input_data = json.loads(job.input_json or "{}")
        program_id = input_data.get("program_id")
        window = input_data.get("window") or {}

        if not program_id:
            raise ValueError("program_id is required in input_json")

        # Fetch program
        program = self.paper_repo.get_research_program(program_id)
        if not program:
            raise ValueError(f"Research program not found: {program_id}")

        if not program.enabled:
            raise ValueError(f"Research program is disabled: {program_id}")

        # Parse config
        source_ids = json.loads(program.source_ids)
        filters = json.loads(program.filters_json) if program.filters_json else {}

        # Emit start event
        ctx.emit_event(
            "ResearchSnapshotStarted",
            payload={"program_id": program_id, "source_count": len(source_ids)},
            entity_refs={"program_id": program_id},
        )

        # Capture papers from database
        capture_id = research_capture_papers(
            ctx=ctx,
            paper_repo=self.paper_repo,
            program_id=program_id,
            source_ids=source_ids,
            filters=filters,
            window_since=window.get("since"),
            window_until=window.get("until"),
        )

        # Ingest capture to create snapshot
        snapshot_id = research_snapshot_ingest(
            ctx=ctx,
            paper_repo=self.paper_repo,
            program_id=program_id,
            raw_capture_ref=capture_id,
            window_since=window.get("since"),
            window_until=window.get("until"),
        )

        # Emit finish event
        ctx.emit_event(
            "ResearchSnapshotFinished",
            payload={"program_id": program_id, "snapshot_id": snapshot_id},
            entity_refs={"program_id": program_id, "snapshot_id": snapshot_id},
        )

        # Return output
        return json.dumps({"snapshot_id": snapshot_id})


class ResearchRunHandler:
    """Handler for research_run jobs

    Computes delta between two research snapshots and stores ResearchBundle artifact.
    """

    def __init__(
        self,
        paper_repo: PaperRepository,
        artifact_repo: ArtifactRepository,
        engine: ResearchRunEngine,
    ) -> None:
        self.paper_repo = paper_repo
        self.artifact_repo = artifact_repo
        self.engine = engine

    def execute(self, job: Job, ctx: RunContext) -> str:
        """Execute research run job

        Args:
            job: Job with input_json containing program_id, snapshot_id, baseline_snapshot_id
            ctx: RunContext with job_repo and data_dir

        Returns:
            output_json with bundle_id and artifact_id

        Raises:
            ValueError: If program or snapshot not found
        """
        # Parse input
        input_data = json.loads(job.input_json or "{}")
        program_id = input_data.get("program_id")
        snapshot_id = input_data.get("snapshot_id")
        baseline_snapshot_id = input_data.get("baseline_snapshot_id")

        if not program_id:
            raise ValueError("program_id is required in input_json")
        if not snapshot_id:
            raise ValueError("snapshot_id is required in input_json")

        # Validate program exists
        program = self.paper_repo.get_research_program(program_id)
        if not program:
            raise ValueError(f"Research program not found: {program_id}")

        # Validate snapshots exist
        snapshot = self.paper_repo.get_research_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        if baseline_snapshot_id:
            baseline = self.paper_repo.get_research_snapshot(baseline_snapshot_id)
            if not baseline:
                raise ValueError(f"Baseline snapshot not found: {baseline_snapshot_id}")

        # Emit start event
        ctx.emit_event(
            "ResearchRunStarted",
            payload={
                "program_id": program_id,
                "snapshot_id": snapshot_id,
                "baseline_snapshot_id": baseline_snapshot_id,
            },
            entity_refs={
                "program_id": program_id,
                "snapshot_id": snapshot_id,
            },
        )

        # Call engine to compute delta
        bundle = self.engine.run(
            program_id=program_id,
            snapshot_id=snapshot_id,
            baseline_snapshot_id=baseline_snapshot_id,
            ctx=ctx,
        )

        # Store bundle as artifact
        input_refs = {
            "snapshot_id": snapshot_id,
        }
        if baseline_snapshot_id:
            input_refs["baseline_snapshot_id"] = baseline_snapshot_id

        artifact_id = self.artifact_repo.put(
            kind="research_bundle",
            schema_version="v1",
            content=bundle,
            producer_engine="ResearchRunEngine",
            producer_version="v1",
            job_id=job.job_id,
            input_refs=input_refs,
            metadata={
                "program_id": program_id,
                "new_count": bundle["metadata"]["new_count"],
                "removed_count": bundle["metadata"]["removed_count"],
                "kept_count": bundle["metadata"]["kept_count"],
            },
        )

        # Emit finish event
        ctx.emit_event(
            "ResearchRunFinished",
            payload={
                "program_id": program_id,
                "bundle_id": bundle["bundle_id"],
                "artifact_id": artifact_id,
                "new_count": bundle["metadata"]["new_count"],
                "removed_count": bundle["metadata"]["removed_count"],
                "kept_count": bundle["metadata"]["kept_count"],
            },
            entity_refs={
                "program_id": program_id,
                "artifact_id": artifact_id,
            },
        )

        # Return output
        return json.dumps({
            "bundle_id": bundle["bundle_id"],
            "artifact_id": artifact_id,
        })
