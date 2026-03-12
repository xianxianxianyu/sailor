"""IssueCompose Job Handler

Handler for issue_compose jobs that orchestrates IssueComposerEngine
and artifact storage.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from core.artifact.repository import ArtifactRepository
from core.models import Job
from core.runner.handlers import RunContext
from .composer import IssueComposerEngine
from .models import FollowSpec

logger = logging.getLogger(__name__)


class IssueComposeHandler:
    """Handler for issue_compose jobs

    Fetches bundle artifacts, calls IssueComposerEngine, and stores
    the resulting IssueSnapshot artifact.
    """

    def __init__(
        self,
        artifact_repo: ArtifactRepository,
        engine: IssueComposerEngine,
    ) -> None:
        self.artifact_repo = artifact_repo
        self.engine = engine

    def execute(self, job: Job, ctx: RunContext) -> str:
        """Execute issue compose job

        Args:
            job: Job with input_json containing follow_spec, window, bundle IDs
            ctx: RunContext with job_repo and data_dir

        Returns:
            output_json with issue_id and artifact_id

        Raises:
            ValueError: If input is invalid or bundles not found
        """
        # Parse input
        input_data = json.loads(job.input_json or "{}")
        follow_spec_data = input_data.get("follow_spec")
        window = input_data.get("window")
        board_bundle_ids = input_data.get("board_bundle_ids", [])
        # Support both singular and plural for backward compatibility
        research_bundle_ids = input_data.get("research_bundle_ids", [])
        if not research_bundle_ids:
            single_id = input_data.get("research_bundle_id")
            if single_id:
                research_bundle_ids = [single_id]

        if not follow_spec_data:
            raise ValueError("follow_spec is required in input_json")
        if not window:
            raise ValueError("window is required in input_json")

        # Build FollowSpec from input
        follow_spec = FollowSpec(
            follow_id=follow_spec_data["follow_id"],
            name=follow_spec_data["name"],
            description=follow_spec_data.get("description"),
            board_ids=follow_spec_data.get("board_ids"),
            research_program_ids=follow_spec_data.get("research_program_ids"),
            enabled=follow_spec_data.get("enabled", True),
        )

        # Fetch bundle artifacts
        research_bundles = []
        for rid in research_bundle_ids:
            artifact = self.artifact_repo.get(rid)
            if not artifact:
                raise ValueError(f"Research bundle not found: {rid}")
            if artifact.kind != "research_bundle":
                raise ValueError(
                    f"Expected research_bundle, got {artifact.kind}: {rid}"
                )
            research_bundles.append(artifact.content)

        board_bundles = []
        for bundle_id in board_bundle_ids:
            artifact = self.artifact_repo.get(bundle_id)
            if not artifact:
                raise ValueError(f"Board bundle not found: {bundle_id}")
            if artifact.kind != "board_bundle":
                raise ValueError(
                    f"Expected board_bundle, got {artifact.kind}: {bundle_id}"
                )
            board_bundles.append(artifact.content)

        # Emit start event
        ctx.emit_event(
            "IssueComposeStarted",
            payload={
                "follow_id": follow_spec.follow_id,
                "research_bundle_ids": research_bundle_ids,
                "board_bundle_ids": board_bundle_ids,
            },
            entity_refs={
                "follow_id": follow_spec.follow_id,
            },
        )

        # Call engine to compose issue (pass first research bundle for now)
        research_bundle = research_bundles[0] if research_bundles else None

        # Call engine to compose issue
        issue_snapshot = self.engine.compose(
            follow_spec=follow_spec,
            window=window,
            research_bundle=research_bundle,
            board_bundles=board_bundles,
            ctx=ctx,
        )

        # Store IssueSnapshot as artifact
        input_refs: dict[str, Any] = {}
        if research_bundle_ids:
            input_refs["research_bundle_ids"] = research_bundle_ids
        if board_bundle_ids:
            input_refs["board_bundle_ids"] = board_bundle_ids

        artifact_id = self.artifact_repo.put(
            kind="issue_snapshot",
            schema_version="v1",
            content=issue_snapshot,
            producer_engine="IssueComposerEngine",
            producer_version="v1",
            job_id=job.job_id,
            input_refs=input_refs,
            metadata={
                "follow_id": follow_spec.follow_id,
                "issue_id": issue_snapshot["issue_id"],
                "total_items": issue_snapshot["metadata"]["total_items"],
                "section_count": issue_snapshot["metadata"]["section_count"],
            },
        )

        # Emit finish event
        ctx.emit_event(
            "IssueComposeFinished",
            payload={
                "follow_id": follow_spec.follow_id,
                "issue_id": issue_snapshot["issue_id"],
                "artifact_id": artifact_id,
                "total_items": issue_snapshot["metadata"]["total_items"],
                "section_count": issue_snapshot["metadata"]["section_count"],
            },
            entity_refs={
                "follow_id": follow_spec.follow_id,
                "artifact_id": artifact_id,
            },
        )

        # Return output
        return json.dumps({
            "issue_id": issue_snapshot["issue_id"],
            "artifact_id": artifact_id,
        })
