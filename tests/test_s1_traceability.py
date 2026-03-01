"""S1 smoke tests — run_id traceability."""
import json
import uuid

from core.models import Job
from core.runner.handlers import RunContext
from core.runner.job_runner import JobRunner


def test_events_stored_under_job_id(job_repo):
    """Events emitted by RunContext should be queryable via job_id."""
    job_id = uuid.uuid4().hex[:12]
    ctx = RunContext(job_repo=job_repo, run_id=job_id)
    ctx.emit_event("TestEvent", {"foo": "bar"})

    events = job_repo.list_events(job_id)
    assert len(events) == 1
    assert events[0].event_type == "TestEvent"


def test_tool_call_lifecycle(job_repo, db):
    """record_tool_call + finish_tool_call round-trip."""
    job_id = uuid.uuid4().hex[:12]
    # Create the parent job so FK constraint is satisfied
    job_repo.create_job(Job(job_id=job_id, job_type="test", input_json="{}"))
    ctx = RunContext(job_repo=job_repo, run_id=job_id)

    tc = ctx.record_tool_call("test_tool", {"input": 1})
    assert tc.status == "pending"

    ctx.finish_tool_call(tc.tool_call_id, "succeeded")
    with db.connect() as conn:
        row = conn.execute(
            "SELECT status FROM tool_calls WHERE tool_call_id = ?", (tc.tool_call_id,)
        ).fetchone()
    assert row["status"] == "succeeded"


def test_call_tool_with_policy_deny(job_repo):
    """call_tool should raise PermissionError when policy denies."""
    from core.runner.handlers import RunContext

    class FakeDecision:
        action = "deny"
        reason = "test"

    def deny_all(tool_name, request, ctx):
        return FakeDecision()

    ctx = RunContext(job_repo=job_repo, run_id="test", policy_check=deny_all)
    raised = False
    try:
        ctx.call_tool("dangerous_tool", {}, lambda r: None)
    except PermissionError:
        raised = True
    assert raised
