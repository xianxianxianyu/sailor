"""S4 smoke tests — platform hardening (WAL, PolicyGate via call_tool)."""
import sqlite3

from core.models import Job
from core.storage.db import Database
from core.runner.handlers import RunContext


def test_wal_mode_enabled(tmp_path):
    db = Database(tmp_path / "wal_test.db")
    db.init_schema()
    conn = db.connect()
    result = conn.execute("PRAGMA journal_mode").fetchone()
    assert result[0] == "wal"
    conn.close()


def test_call_tool_records_and_finishes(job_repo, db):
    # Create the parent job so FK constraint is satisfied
    job_repo.create_job(Job(job_id="test_ct", job_type="test", input_json="{}"))
    ctx = RunContext(job_repo=job_repo, run_id="test_ct")
    result = ctx.call_tool(
        "safe_tool",
        {"key": "value"},
        execute_fn=lambda req: "ok",
    )
    assert result == "ok"
    with db.connect() as conn:
        row = conn.execute(
            "SELECT status FROM tool_calls WHERE run_id = ?", ("test_ct",)
        ).fetchone()
    assert row["status"] == "succeeded"


def test_call_tool_records_failure(job_repo, db):
    # Create the parent job so FK constraint is satisfied
    job_repo.create_job(Job(job_id="test_fail", job_type="test", input_json="{}"))
    ctx = RunContext(job_repo=job_repo, run_id="test_fail")

    raised = False
    try:
        ctx.call_tool(
            "failing_tool",
            {},
            execute_fn=lambda req: (_ for _ in ()).throw(RuntimeError("boom")),
        )
    except RuntimeError:
        raised = True

    assert raised
    with db.connect() as conn:
        row = conn.execute(
            "SELECT status FROM tool_calls WHERE run_id = ?", ("test_fail",)
        ).fetchone()
    assert row["status"] == "failed"


def test_policy_deny_blocks_tool(job_repo, db):
    class DenyDecision:
        action = "deny"
        reason = "blocked"

    ctx = RunContext(
        job_repo=job_repo,
        run_id="test_deny",
        policy_check=lambda t, r, c: DenyDecision(),
    )

    raised = False
    try:
        ctx.call_tool("blocked_tool", {}, execute_fn=lambda r: None)
    except PermissionError:
        raised = True

    assert raised
    # No tool call should be recorded when denied
    with db.connect() as conn:
        row = conn.execute(
            "SELECT count(*) as cnt FROM tool_calls WHERE run_id = ?", ("test_deny",)
        ).fetchone()
    assert row["cnt"] == 0
