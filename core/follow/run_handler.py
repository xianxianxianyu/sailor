"""FollowRunHandler - Handler for follow_run jobs

Triggered by scheduler or manual API call.
Delegates to FollowOrchestrator.
"""
from __future__ import annotations

import json
import logging

from core.follow.orchestrator import FollowOrchestrator
from core.follow.repository import FollowRepository
from core.models import Job
from core.runner.handlers import RunContext

logger = logging.getLogger(__name__)


class FollowRunHandler:
    """Handler for follow_run jobs"""

    def __init__(
        self,
        orchestrator: FollowOrchestrator,
        follow_repo: FollowRepository,
    ) -> None:
        self.orchestrator = orchestrator
        self.follow_repo = follow_repo

    def execute(self, job: Job, ctx: RunContext) -> str:
        """Execute follow run job

        Args:
            job: Job with input_json containing follow_id and optional window
            ctx: RunContext

        Returns:
            output_json with issue_compose_job_id
        """
        # 1. Parse input_json
        input_data = json.loads(job.input_json)
        follow_id = input_data["follow_id"]
        window = input_data.get("window")

        logger.info("[follow-run] Starting follow_id=%s window=%s", follow_id, window)

        # 2. Emit FollowRunStarted event
        ctx.emit_event("FollowRunStarted", {
            "follow_id": follow_id,
            "window": window,
        })

        try:
            # 3. Call orchestrator.run()
            issue_job_id = self.orchestrator.run(follow_id, window)

            # 4. Emit FollowRunFinished event
            ctx.emit_event("FollowRunFinished", {
                "follow_id": follow_id,
                "issue_job_id": issue_job_id,
            })

            logger.info("[follow-run] Completed follow_id=%s issue_job_id=%s", follow_id, issue_job_id)

            # 5. Return output_json with job_id
            return json.dumps({
                "issue_job_id": issue_job_id,
                "follow_id": follow_id,
            })

        except Exception as e:
            logger.exception("[follow-run] Failed follow_id=%s", follow_id)
            ctx.emit_event("FollowRunFailed", {
                "follow_id": follow_id,
                "error": str(e),
            })
            raise
