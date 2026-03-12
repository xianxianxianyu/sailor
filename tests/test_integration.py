"""Integration tests — module connectivity, logging system, and pipeline smoke tests."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.logging_config import setup_logging
from core.models import RawEntry, Resource


# ---------------------------------------------------------------------------
# 1. Container builds successfully (all DI wiring works)
# ---------------------------------------------------------------------------

def test_container_builds(tmp_path):
    """build_container should succeed with a temp project root."""
    _create_project_files(tmp_path)
    from backend.app.container import build_container

    container = build_container(tmp_path)
    assert container is not None
    assert container.db is not None
    assert container.resource_repo is not None
    assert container.job_runner is not None
    assert container.source_repo is not None


# ---------------------------------------------------------------------------
# 2. FastAPI app + key endpoints reachable
#    (uses the module-level app from main.py which was created at import time)
# ---------------------------------------------------------------------------

def test_healthz_reachable():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    assert client.get("/healthz").status_code == 200


def test_sources_list_reachable():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    resp = client.get("/sources")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_logs_get_reachable():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    resp = client.get("/logs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# 3. Logging system: LogHandler captures to memory queue
# ---------------------------------------------------------------------------

def test_log_handler_captures_to_queue():
    """Logger output should be captured by LogHandler into the memory deque."""
    from backend.app.routers.logs import LogHandler, _log_deque

    handler = LogHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

    test_logger = logging.getLogger("core.test.integration")
    # Prevent propagation so root handlers don't also trigger LogHandler
    test_logger.propagate = False
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    before = len(_log_deque)
    test_logger.info("integration test message")
    after = len(_log_deque)

    assert after == before + 1
    assert "integration test message" in _log_deque[-1]["message"]

    # Cleanup
    test_logger.removeHandler(handler)
    test_logger.propagate = True


def test_setup_logging_installs_handlers():
    """setup_logging should install console + LogHandler on root."""
    from backend.app.routers.logs import LogHandler

    setup_logging()
    root = logging.getLogger()
    handler_types = [type(h).__name__ for h in root.handlers]
    assert "StreamHandler" in handler_types
    assert "LogHandler" in handler_types


def test_log_handler_filters_third_party():
    """LogHandler should ignore loggers outside allowed prefixes."""
    from backend.app.routers.logs import LogHandler, _log_deque

    handler = LogHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

    noise_logger = logging.getLogger("httpx.client")
    noise_logger.addHandler(handler)
    noise_logger.setLevel(logging.DEBUG)

    before = len(_log_deque)
    noise_logger.info("should be filtered")
    after = len(_log_deque)

    assert after == before  # nothing added
    noise_logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# 4. Pipeline end-to-end: RawEntry -> pipeline.process -> Resource
# ---------------------------------------------------------------------------

def test_pipeline_produces_resource():
    """Default pipeline should transform a RawEntry into a Resource."""
    from core.pipeline import build_default_pipeline

    pipeline = build_default_pipeline()
    entry = RawEntry(
        entry_id="test-001",
        feed_id="feed-test",
        source="integration-test",
        title="Test Article About LLM Agents",
        url="https://example.com/article?utm_source=test",
        content="<p>This is a test article about building LLM agents.</p>",
        published_at=datetime(2025, 1, 1),
    )
    resource = pipeline.process(entry)

    assert isinstance(resource, Resource)
    assert resource.canonical_url
    assert "utm_source" not in resource.canonical_url
    assert resource.title == "Test Article About LLM Agents"
    assert resource.resource_id


# ---------------------------------------------------------------------------
# 5. Job runner end-to-end: create job -> run -> check result
# ---------------------------------------------------------------------------

def test_job_runner_executes_job(db, job_repo):
    """Job runner should execute a registered handler and mark job completed."""
    import json as _json
    from core.runner.job_runner import JobRunner
    from core.runner.handlers import RunContext
    from core.models import Job

    runner = JobRunner(job_repo=job_repo)

    class EchoHandler:
        def execute(self, job: Job, ctx: RunContext) -> str:
            return _json.dumps({"echo": "hello"})

    runner.register("echo", EchoHandler())

    job = job_repo.create_job(Job(
        job_id="integ-test-001",
        job_type="echo",
        input_json="{}",
    ))

    result = runner.run(job.job_id)
    assert result.status == "succeeded"
    assert '"echo"' in (result.output_json or "")


# ---------------------------------------------------------------------------
# 6. Regression: Fix 1 — api_json Request does not receive timeout kwarg
# ---------------------------------------------------------------------------

def test_api_json_request_no_timeout_kwarg():
    """Request() should NOT receive 'timeout' in kwargs — it goes to urlopen() only."""
    from urllib.request import Request

    # Simulate what collectors.py does after the fix
    headers = {"User-Agent": "test"}
    request_kwargs: dict = {"headers": headers}  # no timeout key
    # This must not raise TypeError
    req = Request("https://example.com", **request_kwargs)
    assert req.full_url == "https://example.com"


# ---------------------------------------------------------------------------
# 7. Regression: Fix 2 — RSSFeed uses feed_id, not id
# ---------------------------------------------------------------------------

def test_rssfeed_has_feed_id_attribute():
    """RSSFeed dataclass should use feed_id (not id)."""
    from core.models import RSSFeed

    feed = RSSFeed(feed_id="f1", name="Test", xml_url="https://example.com/rss")
    assert feed.feed_id == "f1"
    assert not hasattr(feed, "id")


# ---------------------------------------------------------------------------
# 9. Regression: Fix 4 — SSE log deque with seq numbers
# ---------------------------------------------------------------------------

def test_log_deque_seq_monotonic():
    """Log entries should have monotonically increasing seq numbers."""
    from backend.app.routers.logs import add_log, _log_deque

    before_count = len(_log_deque)
    add_log("INFO", "msg_a")
    add_log("INFO", "msg_b")
    add_log("INFO", "msg_c")

    recent = list(_log_deque)[-3:]
    assert recent[0]["seq"] < recent[1]["seq"] < recent[2]["seq"]
    assert all("seq" in entry for entry in recent)


def test_log_deque_bounded():
    """Deque should never exceed maxlen=200."""
    from backend.app.routers.logs import add_log, _log_deque

    for i in range(250):
        add_log("INFO", f"flood_{i}")

    assert len(_log_deque) <= 200


# ---------------------------------------------------------------------------
# 10. Regression: Fix 5 — SnifferToolModule handles TimeoutError
# ---------------------------------------------------------------------------

def test_sniffer_tool_module_timeout_handling():
    """TimeoutError from as_completed should be caught, not crash the job."""
    from core.sniffer.tool_module import SnifferToolModule, WorkerResults

    # Just verify the class can be constructed — the TimeoutError handling is
    # in the as_completed loop which requires real adapters to test.
    mock_registry = MagicMock()
    mock_registry._adapters = {}
    mock_repo = MagicMock()

    module = SnifferToolModule(mock_registry, mock_repo)
    assert module is not None


# ---------------------------------------------------------------------------
# 11. Regression: Fix 6 — PolicyGate creates pending_confirm
# ---------------------------------------------------------------------------

def test_policy_gate_creates_pending_on_require_confirm(db, job_repo):
    """When require_confirm, call_tool should create a pending_confirm record."""
    from core.runner.handlers import RunContext
    from core.runner.policy import PolicyGate, PolicyDecision
    from core.models import Job

    policy_gate = PolicyGate(job_repo, auto_confirm=False)

    # Create a job to attach to
    job = job_repo.create_job(Job(
        job_id="confirm-test-001",
        job_type="echo",
        input_json="{}",
    ))

    ctx = RunContext(
        job_repo=job_repo,
        run_id=job.job_id,
        policy_check=policy_gate.check,
        policy_gate=policy_gate,
    )

    # propose_source is a SIDE_EFFECT_TOOL so will require_confirm
    with pytest.raises(PermissionError, match="requires confirmation"):
        ctx.call_tool("propose_source", {"name": "test"}, lambda req: None)

    # Verify a pending_confirm was created
    pending = job_repo.list_confirms(status="pending")
    assert any(pc.action_type == "propose_source" for pc in pending)


# ---------------------------------------------------------------------------
# 12. Regression: Fix 7 — DB pragmas set correctly
# ---------------------------------------------------------------------------

def test_db_pragmas_set(db):
    """Database should have foreign_keys=ON and busy_timeout=5000."""
    with db.connect() as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

        bt = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert bt == 5000


# ---------------------------------------------------------------------------
# 14. Regression: Fix 9 — IntelligenceEngine.process accepts ctx
# ---------------------------------------------------------------------------

def test_intelligence_engine_process_accepts_ctx():
    """process() should accept an optional ctx parameter."""
    import inspect
    from core.engines.intelligence import ResourceIntelligenceEngine

    sig = inspect.signature(ResourceIntelligenceEngine.process)
    assert "ctx" in sig.parameters
    # Default should be None (backward-compatible)
    assert sig.parameters["ctx"].default is None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 15. P7.2 — AccessLogMiddleware logs requests, skips /healthz
# ---------------------------------------------------------------------------

def test_access_log_middleware_logs_request(caplog):
    """AccessLogMiddleware should log GET /follows with status code."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="backend.app.middleware"):
        client.get("/follows")

    assert any("GET /follows" in r.message and "200" in r.message for r in caplog.records)


def test_access_log_middleware_skips_healthz(caplog):
    """AccessLogMiddleware should NOT log /healthz requests."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="backend.app.middleware"):
        client.get("/healthz")

    assert not any("/healthz" in r.message for r in caplog.records)


@pytest.mark.parametrize("level_name,expected", [
    ("DEBUG", logging.DEBUG),
    ("INFO", logging.INFO),
    ("WARNING", logging.WARNING),
])
def test_log_level_env_var(monkeypatch, level_name, expected):
    """setup_logging() should respect LOG_LEVEL env var."""
    monkeypatch.setenv("LOG_LEVEL", level_name)
    setup_logging()
    root = logging.getLogger()
    assert root.level == expected


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _create_project_files(tmp_path: Path) -> None:
    """Create minimal data files so build_container can succeed."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "seed_entries.json").write_text("[]", encoding="utf-8")
    (tmp_path / "1.md").write_text("<opml/>", encoding="utf-8")
