"""FollowOrchestrator - Workflow coordination for Follow runs

Orchestrates multi-step pipeline:
1. Board snapshots (parallel for each board)
2. Board runs (parallel, compute deltas)
3. Research run (single job)
4. Issue compose (final composition)
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta

import logging

from core.artifact.repository import ArtifactRepository
from core.board.repository import BoardRepository
from core.follow.models import Follow
from core.follow.repository import FollowRepository
from core.models import Job
from core.paper.repository import PaperRepository
from core.storage.job_repository import JobRepository

logger = logging.getLogger(__name__)


class FollowOrchestrator:
    """Orchestrates Follow run workflow"""

    def __init__(
        self,
        follow_repo: FollowRepository,
        board_repo: BoardRepository,
        paper_repo: PaperRepository,
        artifact_repo: ArtifactRepository,
        job_repo: JobRepository,
        job_runner=None,
    ) -> None:
        self.follow_repo = follow_repo
        self.board_repo = board_repo
        self.paper_repo = paper_repo
        self.artifact_repo = artifact_repo
        self.job_repo = job_repo
        self.job_runner = job_runner

    def run(
        self,
        follow_id: str,
        window: dict[str, str] | None = None,
    ) -> str:
        """Trigger a Follow run

        Args:
            follow_id: Follow ID to run
            window: Optional time window override {"since": ISO, "until": ISO}

        Returns:
            job_id: The final issue_compose job ID

        Raises:
            ValueError: If Follow not found or disabled
        """
        # 1. Validate Follow exists and is enabled
        follow = self.follow_repo.get_follow(follow_id)
        if not follow:
            raise ValueError(f"Follow not found: {follow_id}")
        if not follow.enabled:
            raise ValueError(f"Follow is disabled: {follow_id}")

        # 2. Compute window (use override or policy)
        window_dict = self._compute_window(follow, window)

        # 3. Create board_snapshot jobs (idempotent)
        board_ids = follow.board_ids or []
        snapshot_ids = self._create_board_snapshot_jobs(board_ids, window_dict)

        # 4. Create board_run jobs (idempotent)
        board_bundle_ids = self._create_board_run_jobs(board_ids, snapshot_ids, window_dict)

        # 5. Create research_snapshot jobs (idempotent)
        program_ids = follow.research_program_ids or []
        research_snapshot_ids = self._create_research_snapshot_jobs(program_ids, window_dict)

        # 6. Create research_run jobs (idempotent)
        research_bundle_ids = self._create_research_run_jobs(program_ids, research_snapshot_ids, window_dict)

        # 7. Create issue_compose job (idempotent)
        issue_job_id = self._create_issue_compose_job(
            follow, window_dict,
            board_bundle_ids=board_bundle_ids,
            research_bundle_ids=research_bundle_ids,
        )

        # 8. Update follow.last_run_at
        self.follow_repo.update_last_run(follow_id, datetime.utcnow())

        # 9. Return issue_compose job_id
        return issue_job_id

    def _run_job(self, job_id: str, is_new: bool) -> None:
        """Execute a job via job_runner if available.

        Runs the job if it's new, or if it exists but hasn't succeeded yet.
        """
        if not self.job_runner:
            return

        if is_new:
            self.job_runner.run(job_id)
            return

        # Job already exists — check if it needs re-running
        job = self.job_repo.get_job(job_id)
        if job and job.status not in ("succeeded", "running"):
            # Reset to queued so runner can pick it up
            self.job_repo.update_status(job_id, "queued")
            self.job_runner.run(job_id)

    def _compute_window(self, follow: Follow, override: dict[str, str] | None) -> dict[str, str]:
        """Compute time window from policy or override"""
        if override:
            return override

        now = datetime.utcnow()
        if follow.window_policy == "daily":
            since = (now - timedelta(days=1)).isoformat()
        elif follow.window_policy == "weekly":
            since = (now - timedelta(days=7)).isoformat()
        elif follow.window_policy == "monthly":
            since = (now - timedelta(days=30)).isoformat()
        else:
            since = (now - timedelta(days=1)).isoformat()

        return {"since": since, "until": now.isoformat()}

    def _create_board_snapshot_jobs(
        self,
        board_ids: list[str],
        window: dict[str, str],
    ) -> list[str]:
        """Create board_snapshot jobs for each board

        Returns:
            List of snapshot_ids (deterministic)
        """
        snapshot_ids = []

        for board_id in board_ids:
            # Generate deterministic snapshot_id
            captured_at = datetime.fromisoformat(window["until"])
            snapshot_id = self._generate_snapshot_id(board_id, captured_at)
            snapshot_ids.append(snapshot_id)

            # Create idempotent job
            idempotency_key = f"board_snapshot:{board_id}:{window['until']}"
            input_data = {
                "board_id": board_id,
                "window": window,
            }

            job_id, is_new = self.job_repo.create_job_idempotent(
                idempotency_key=idempotency_key,
                job_type="board_snapshot",
                input_json=input_data,
            )

            # Execute the job
            self._run_job(job_id, is_new)

        return snapshot_ids

    def _create_board_run_jobs(
        self,
        board_ids: list[str],
        snapshot_ids: list[str],
        window: dict[str, str],
    ) -> list[str]:
        """Create board_run jobs for each board

        Returns:
            List of board_bundle artifact IDs (from job outputs)
        """
        artifact_ids = []

        for board_id, snapshot_id in zip(board_ids, snapshot_ids):
            # Find baseline snapshot
            baseline_id = self._find_baseline_snapshot(board_id, window)

            # Create idempotent job
            idempotency_key = f"board_run:{board_id}:{window['since']}:{window['until']}"
            input_data = {
                "board_id": board_id,
                "snapshot_id": snapshot_id,
                "baseline_snapshot_id": baseline_id,
                "window": window,
            }

            job_id, is_new = self.job_repo.create_job_idempotent(
                idempotency_key=idempotency_key,
                job_type="board_run",
                input_json=input_data,
            )

            # Execute the job
            self._run_job(job_id, is_new)

            # Extract artifact_id from job output
            job = self.job_repo.get_job(job_id)
            if job and job.output_json:
                output = json.loads(job.output_json)
                artifact_id = output.get("artifact_id")
                if artifact_id:
                    artifact_ids.append(artifact_id)
                else:
                    logger.warning("[orchestrator] board_run job %s has no artifact_id in output", job_id)
            else:
                logger.warning("[orchestrator] board_run job %s has no output", job_id)

        return artifact_ids

    def _create_research_snapshot_jobs(
        self,
        program_ids: list[str],
        window: dict[str, str],
    ) -> list[str]:
        """Create research_snapshot jobs for each program

        Returns:
            List of snapshot_ids (from job outputs)
        """
        snapshot_ids = []

        for program_id in program_ids:
            idempotency_key = f"research_snapshot:{program_id}:{window['until']}"
            input_data = {
                "program_id": program_id,
                "window": window,
            }

            job_id, is_new = self.job_repo.create_job_idempotent(
                idempotency_key=idempotency_key,
                job_type="research_snapshot",
                input_json=input_data,
            )

            # Execute the job
            self._run_job(job_id, is_new)

            # Extract snapshot_id from job output
            job = self.job_repo.get_job(job_id)
            if job and job.output_json:
                output = json.loads(job.output_json)
                sid = output.get("snapshot_id")
                if sid:
                    snapshot_ids.append(sid)
                    continue

            logger.warning("[orchestrator] research_snapshot job %s has no snapshot_id", job_id)
            snapshot_ids.append(None)

        return snapshot_ids

    def _create_research_run_jobs(
        self,
        program_ids: list[str],
        snapshot_ids: list,
        window: dict[str, str],
    ) -> list[str]:
        """Create research_run jobs for each program

        Returns:
            List of research_bundle artifact IDs (from job outputs)
        """
        artifact_ids = []

        for program_id, snapshot_id in zip(program_ids, snapshot_ids):
            if not snapshot_id:
                logger.warning("[orchestrator] Skipping research_run for %s: no snapshot", program_id)
                continue

            # Find baseline snapshot
            baseline_id = self._find_baseline_research_snapshot(program_id, window)

            idempotency_key = f"research_run:{program_id}:{window['since']}:{window['until']}"
            input_data = {
                "program_id": program_id,
                "snapshot_id": snapshot_id,
                "baseline_snapshot_id": baseline_id,
            }

            job_id, is_new = self.job_repo.create_job_idempotent(
                idempotency_key=idempotency_key,
                job_type="research_run",
                input_json=input_data,
            )

            # Execute the job
            self._run_job(job_id, is_new)

            # Extract artifact_id from job output
            job = self.job_repo.get_job(job_id)
            if job and job.output_json:
                output = json.loads(job.output_json)
                artifact_id = output.get("artifact_id")
                if artifact_id:
                    artifact_ids.append(artifact_id)
                    continue

            logger.warning("[orchestrator] research_run job %s has no artifact_id", job_id)

        return artifact_ids

    def _find_baseline_research_snapshot(self, program_id: str, window: dict[str, str]) -> str | None:
        """Find the most recent research snapshot before the current window"""
        since_dt = datetime.fromisoformat(window["since"])

        snapshots = self.paper_repo.list_research_snapshots(
            program_id=program_id,
            limit=1,
        )

        for snapshot in snapshots:
            if snapshot.captured_at and snapshot.captured_at < since_dt:
                return snapshot.snapshot_id

        return None

    def _create_issue_compose_job(
        self,
        follow: Follow,
        window: dict[str, str],
        board_bundle_ids: list[str],
        research_bundle_ids: list[str],
    ) -> str:
        """Create issue_compose job

        Returns:
            job_id of the issue_compose job
        """
        # Create idempotent job
        idempotency_key = f"issue_compose:{follow.follow_id}:{window['since']}:{window['until']}"
        input_data = {
            "follow_spec": {
                "follow_id": follow.follow_id,
                "name": follow.name,
                "description": follow.description,
                "board_ids": follow.board_ids or [],
                "research_program_ids": follow.research_program_ids or [],
                "enabled": follow.enabled,
            },
            "window": window,
            "board_bundle_ids": board_bundle_ids,
            "research_bundle_ids": research_bundle_ids,
        }

        job_id, is_new = self.job_repo.create_job_idempotent(
            idempotency_key=idempotency_key,
            job_type="issue_compose",
            input_json=input_data,
        )

        # Execute the job
        self._run_job(job_id, is_new)

        return job_id

    def _find_baseline_snapshot(self, board_id: str, window: dict[str, str]) -> str | None:
        """Find the most recent snapshot before the current window

        Used as baseline for delta computation.
        """
        since_dt = datetime.fromisoformat(window["since"])

        # Query snapshots before window start
        snapshots = self.board_repo.list_snapshots(
            board_id=board_id,
            limit=1,
        )

        for snapshot in snapshots:
            if snapshot.captured_at < since_dt:
                return snapshot.snapshot_id

        return None

    def _generate_snapshot_id(self, board_id: str, captured_at: datetime) -> str:
        """Generate deterministic snapshot_id"""
        key = f"{board_id}:{captured_at.isoformat()}".encode("utf-8")
        hash_hex = hashlib.sha256(key).hexdigest()[:16]
        return f"snap_{hash_hex}"

    def _generate_bundle_id(self, bundle_type: str, ref_id: str, window: dict[str, str]) -> str:
        """Generate deterministic bundle artifact ID"""
        key = f"{bundle_type}:{ref_id}:{window['since']}:{window['until']}".encode("utf-8")
        hash_hex = hashlib.sha256(key).hexdigest()[:16]
        return f"{bundle_type}_bundle_{hash_hex}"
