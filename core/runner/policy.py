from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from core.models import PendingConfirm
from core.storage.job_repository import JobRepository
from core.runner.handlers import RunContext

SIDE_EFFECT_TOOLS = frozenset({
    "propose_source", "import_feeds", "upsert_source",
    "run_source", "delete_source",
})


@dataclass
class PolicyDecision:
    action: str       # "allow" | "deny" | "require_confirm"
    reason: str = ""


class PolicyGate:
    """Pre-tool-call policy check."""

    def __init__(self, job_repo: JobRepository, auto_confirm: bool = False) -> None:
        self.job_repo = job_repo
        self.auto_confirm = auto_confirm

    def check(self, tool_name: str, request: dict, ctx: RunContext) -> PolicyDecision:
        if tool_name in SIDE_EFFECT_TOOLS:
            decision = PolicyDecision(
                "allow" if self.auto_confirm else "require_confirm",
                reason=f"side-effect tool: {tool_name}",
            )
        else:
            decision = PolicyDecision("allow")

        ctx.emit_event("PolicyDecision", payload={
            "tool_name": tool_name,
            "action": decision.action,
            "reason": decision.reason,
        })
        return decision

    def create_pending(self, action_type: str, payload: dict,
                       job_id: str | None = None) -> PendingConfirm:
        pc = PendingConfirm(
            confirm_id=uuid.uuid4().hex[:12],
            job_id=job_id,
            action_type=action_type,
            payload_json=json.dumps(payload),
        )
        return self.job_repo.create_confirm(pc)
