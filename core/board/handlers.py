"""BoardEngine Job Handlers

Job handlers for board snapshot operations.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from core.artifact.repository import ArtifactRepository
from core.board.engine import BoardRunEngine
from core.board.repository import BoardRepository
from core.board.tools import (
    boards_capture_github,
    boards_capture_huggingface,
    boards_snapshot_ingest,
)
from core.models import Job
from core.runner.handlers import RunContext

logger = logging.getLogger(__name__)


class BoardSnapshotHandler:
    """Handler for board_snapshot jobs

    Orchestrates capture + ingest to create board snapshots.
    """

    def __init__(self, board_repo: BoardRepository) -> None:
        self.board_repo = board_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        """Execute board snapshot job

        Args:
            job: Job with input_json containing board_id and optional window
            ctx: RunContext with job_repo and data_dir

        Returns:
            output_json with snapshot_id

        Raises:
            ValueError: If board not found or provider unsupported
        """
        # Parse input
        input_data = json.loads(job.input_json or "{}")
        board_id = input_data.get("board_id")
        window = input_data.get("window") or {}

        if not board_id:
            raise ValueError("board_id is required in input_json")

        # Fetch board
        board = self.board_repo.get_board(board_id)
        if not board:
            raise ValueError(f"Board not found: {board_id}")

        # Parse config
        config = json.loads(board.config_json)

        # Emit start event
        ctx.emit_event(
            "BoardSnapshotStarted",
            payload={"board_id": board_id, "provider": board.provider},
            entity_refs={"board_id": board_id},
        )

        # Call appropriate capture function based on provider
        capture_id: str

        if board.provider == "github":
            language = config.get("language")
            since = window.get("since", "daily")
            capture_id = boards_capture_github(ctx, board_id, language, since)

        elif board.provider == "huggingface":
            kind = config.get("kind", "models")
            limit = config.get("limit", 30)
            capture_id = boards_capture_huggingface(ctx, board_id, kind, limit)

        else:
            raise ValueError(f"Unsupported provider: {board.provider}")

        # Ingest capture to create snapshot
        snapshot_id = boards_snapshot_ingest(
            ctx=ctx,
            board_repo=self.board_repo,
            board_id=board_id,
            raw_capture_ref=capture_id,
            window_since=window.get("since"),
            window_until=window.get("until"),
        )

        # Emit finish event
        ctx.emit_event(
            "BoardSnapshotFinished",
            payload={"board_id": board_id, "snapshot_id": snapshot_id},
            entity_refs={"board_id": board_id, "snapshot_id": snapshot_id},
        )

        # Return output
        return json.dumps({"snapshot_id": snapshot_id})


class BoardRunHandler:
    """Handler for board_run jobs

    Computes delta between two board snapshots and stores BoardBundle artifact.
    """

    def __init__(
        self,
        board_repo: BoardRepository,
        artifact_repo: ArtifactRepository,
        engine: BoardRunEngine,
    ) -> None:
        self.board_repo = board_repo
        self.artifact_repo = artifact_repo
        self.engine = engine

    def execute(self, job: Job, ctx: RunContext) -> str:
        """Execute board run job

        Args:
            job: Job with input_json containing board_id, snapshot_id, baseline_snapshot_id
            ctx: RunContext with job_repo and data_dir

        Returns:
            output_json with bundle_id and artifact_id

        Raises:
            ValueError: If board or snapshot not found
        """
        # Parse input
        input_data = json.loads(job.input_json or "{}")
        board_id = input_data.get("board_id")
        snapshot_id = input_data.get("snapshot_id")
        baseline_snapshot_id = input_data.get("baseline_snapshot_id")

        if not board_id:
            raise ValueError("board_id is required in input_json")
        if not snapshot_id:
            raise ValueError("snapshot_id is required in input_json")

        # Validate board exists
        board = self.board_repo.get_board(board_id)
        if not board:
            raise ValueError(f"Board not found: {board_id}")

        # Validate snapshots exist
        snapshot = self.board_repo.get_snapshot(snapshot_id)
        if not snapshot:
            # Snapshot ID from orchestrator may not match actual ID.
            # Fall back to latest snapshot for this board.
            snapshots = self.board_repo.list_snapshots(board_id=board_id, limit=1)
            if snapshots:
                snapshot = snapshots[0]
                snapshot_id = snapshot.snapshot_id
                logger.info("[board-run] Using latest snapshot %s for board %s", snapshot_id, board_id)
            else:
                raise ValueError(f"No snapshots found for board: {board_id}")

        if baseline_snapshot_id:
            baseline = self.board_repo.get_snapshot(baseline_snapshot_id)
            if not baseline:
                raise ValueError(f"Baseline snapshot not found: {baseline_snapshot_id}")

        # Emit start event
        ctx.emit_event(
            "BoardRunStarted",
            payload={
                "board_id": board_id,
                "snapshot_id": snapshot_id,
                "baseline_snapshot_id": baseline_snapshot_id,
            },
            entity_refs={
                "board_id": board_id,
                "snapshot_id": snapshot_id,
            },
        )

        # Call engine to compute delta
        bundle = self.engine.run(
            board_id=board_id,
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
            kind="board_bundle",
            schema_version="v1",
            content=bundle,
            producer_engine="BoardRunEngine",
            producer_version="v1",
            job_id=job.job_id,
            input_refs=input_refs,
            metadata={
                "board_id": board_id,
                "new_count": bundle["metadata"]["new_count"],
                "removed_count": bundle["metadata"]["removed_count"],
                "kept_count": bundle["metadata"]["kept_count"],
            },
        )

        # Emit finish event
        ctx.emit_event(
            "BoardRunFinished",
            payload={
                "board_id": board_id,
                "bundle_id": bundle["bundle_id"],
                "artifact_id": artifact_id,
                "new_count": bundle["metadata"]["new_count"],
                "removed_count": bundle["metadata"]["removed_count"],
                "kept_count": bundle["metadata"]["kept_count"],
            },
            entity_refs={
                "board_id": board_id,
                "artifact_id": artifact_id,
            },
        )

        # Return output
        return json.dumps({
            "bundle_id": bundle["bundle_id"],
            "artifact_id": artifact_id,
        })
