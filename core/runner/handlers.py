from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Protocol, runtime_checkable

from core.models import ProvenanceEvent, ToolCall
from core.storage.job_repository import JobRepository


@runtime_checkable
class JobHandler(Protocol):
    def execute(self, job: Any, ctx: RunContext) -> str | None:
        """Execute the job. Return output_json or None. Raise on failure."""
        ...


@dataclass
class RunContext:
    """Convenience wrapper for provenance writes during job execution."""
    job_repo: JobRepository
    run_id: str
    policy_check: Callable[[str, dict, RunContext], Any] | None = field(default=None, repr=False)
    policy_gate: Any | None = field(default=None, repr=False)

    def emit_event(
        self, event_type: str, payload: dict[str, Any] | None = None,
        entity_refs: dict[str, Any] | None = None, actor: str = "system",
    ) -> None:
        self.job_repo.append_event(ProvenanceEvent(
            event_id=uuid.uuid4().hex[:12],
            run_id=self.run_id,
            event_type=event_type,
            actor=actor,
            entity_refs=entity_refs or {},
            payload=payload or {},
        ))

    def record_tool_call(
        self, tool_name: str, request: dict[str, Any] | str | None = None,
        idempotency_key: str | None = None,
    ) -> ToolCall:
        tc = ToolCall(
            tool_call_id=uuid.uuid4().hex[:12],
            run_id=self.run_id,
            tool_name=tool_name,
            request_json=json.dumps(request) if isinstance(request, dict) else (request or "{}"),
            idempotency_key=idempotency_key,
            started_at=datetime.utcnow(),
        )
        self.job_repo.record_tool_call(tc)
        return tc

    def finish_tool_call(
        self, tc_id: str, status: str, *,
        output_ref: str | None = None, error: str | None = None,
    ) -> None:
        self.job_repo.finish_tool_call(tc_id, status, output_ref=output_ref, error=error)

    def call_tool(
        self, tool_name: str, request: dict[str, Any],
        execute_fn: Callable[[dict[str, Any]], Any],
        idempotency_key: str | None = None,
    ) -> Any:
        """PolicyGate check → record ToolCall → execute → finish ToolCall."""
        if self.policy_check is not None:
            decision = self.policy_check(tool_name, request, self)
            if getattr(decision, "action", "allow") == "deny":
                self.emit_event("ToolCallDenied", {
                    "tool_name": tool_name,
                    "reason": getattr(decision, "reason", ""),
                })
                raise PermissionError(f"Policy denied tool: {tool_name}")
            if getattr(decision, "action", "allow") == "require_confirm":
                self.emit_event("ToolCallRequiresConfirm", {"tool_name": tool_name})
                # Create a pending_confirm record so confirms API can query it
                if self.policy_gate is not None:
                    self.policy_gate.create_pending(
                        action_type=tool_name,
                        payload=request,
                        job_id=self.run_id,
                    )
                raise PermissionError(f"Tool requires confirmation: {tool_name}")

        tc = self.record_tool_call(tool_name, request, idempotency_key=idempotency_key)
        try:
            result = execute_fn(request)
            self.finish_tool_call(tc.tool_call_id, "succeeded")
            return result
        except Exception as exc:
            self.finish_tool_call(tc.tool_call_id, "failed", error=str(exc)[:500])
            raise
