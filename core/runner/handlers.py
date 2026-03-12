from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from core.models import ProvenanceEvent, ToolCall
from core.storage.job_repository import JobRepository


@runtime_checkable
class JobHandler(Protocol):
    def execute(self, job: Any, ctx: RunContext) -> str | None:
        """Execute the job. Return output_json or None. Raise on failure."""
        ...


class JobCancelled(Exception):
    """Raised by cooperative handlers to stop a job without marking it failed."""


@dataclass
class RunContext:
    """Convenience wrapper for provenance writes during job execution."""

    job_repo: JobRepository
    run_id: str
    policy_check: Callable[[str, dict, RunContext], Any] | None = field(default=None, repr=False)
    policy_gate: Any | None = field(default=None, repr=False)
    data_dir: Path | None = None

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

    def is_cancel_requested(self) -> bool:
        job = self.job_repo.get_job(self.run_id)
        if not job:
            return False
        if job.status == "cancelled":
            return True
        return bool(job.metadata.get("cancel_requested"))

    def raise_if_cancel_requested(self, message: str = "Job cancelled") -> None:
        if self.is_cancel_requested():
            raise JobCancelled(message)

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
        """PolicyGate check ? record ToolCall ? execute ? finish ToolCall."""
        self.raise_if_cancel_requested()
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
            self.raise_if_cancel_requested()
            return result
        except Exception as exc:
            self.finish_tool_call(tc.tool_call_id, "failed", error=str(exc)[:500])
            raise

    def call_tool_with_trace(
        self,
        tool_name: str,
        request: dict[str, Any],
        execute_fn: Callable[[dict[str, Any]], Any],
        idempotency_key: str | None = None,
    ) -> tuple[ToolCall, Any]:
        """Like call_tool(), but returns the ToolCall record for raw-capture linkage."""
        self.raise_if_cancel_requested()
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
            self.raise_if_cancel_requested()
            return tc, result
        except Exception as exc:
            self.finish_tool_call(tc.tool_call_id, "failed", error=str(exc)[:500])
            raise

    def save_raw_capture(
        self,
        content: str,
        channel: str,
        content_type: str = "json",
        tool_call_id: str | None = None,
    ) -> str:
        """Write file + write raw_captures table, return capture_id"""
        if self.data_dir is None:
            raise ValueError("data_dir not set in RunContext")

        capture_id = f"cap_{uuid.uuid4().hex[:12]}"
        capture_dir = self.data_dir / "raw_captures"
        capture_dir.mkdir(parents=True, exist_ok=True)
        ext = content_type if content_type and content_type.isascii() else "json"
        ext = "".join(ch for ch in ext if ch.isalnum()).lower() or "json"
        file_path = capture_dir / f"{capture_id}.{ext}"
        file_path.write_text(content, encoding="utf-8")

        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        self.job_repo.save_raw_capture(
            capture_id=capture_id,
            tool_call_id=tool_call_id,
            channel=channel,
            content_ref=str(file_path),
            checksum=checksum,
            content_type=content_type,
        )
        return capture_id

    def load_raw_capture(self, capture_id: str) -> str:
        """Read raw capture content from file"""
        rc = self.job_repo.get_raw_capture(capture_id)
        if not rc:
            raise ValueError(f"RawCapture not found: {capture_id}")
        return Path(rc.content_ref).read_text(encoding="utf-8")
