"""PaperSourceHandler state-reset tests (P0-6)."""
from __future__ import annotations

import json

from core.models import Job
from core.paper.handler import PaperSourceHandler
from core.paper.models import PaperSyncResult
from core.paper.port import PaperSyncPort
from core.paper.repository import PaperRepository
from core.runner.handlers import RunContext


def test_success_resets_source_state_even_when_cursor_empty(db, job_repo, monkeypatch):
    paper_repo = PaperRepository(db)

    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test",
        config_json="{}",
        cursor_json=json.dumps({"start": 0}),
        enabled=True,
    )

    # Seed an errored state
    paper_repo.update_source(source.source_id, error_count=3, last_error="boom")

    class StubSyncPort(PaperSyncPort):
        def sync(self, source, raw):  # type: ignore[override]
            return PaperSyncResult(papers=[], next_cursor_json={}, metrics_json={"ok": True})

    # Avoid real HTTP/tool layer; this test focuses on success-path state reset.
    monkeypatch.setattr(
        "core.paper.handler.paper_fetch_arxiv_atom",
        lambda ctx, src: ("cap_test", "<feed/>"),
    )

    handler = PaperSourceHandler(paper_repo=paper_repo, sync_port=StubSyncPort())

    job_id = "job_p0_6"
    job_repo.create_job(
        Job(
            job_id=job_id,
            job_type="paper_source_run",
            input_json=json.dumps({"source_id": source.source_id}),
        )
    )
    ctx = RunContext(job_repo=job_repo, run_id=job_id)

    handler.execute(
        Job(
            job_id=job_id,
            job_type="paper_source_run",
            input_json=json.dumps({"source_id": source.source_id}),
        ),
        ctx,
    )

    after = paper_repo.get_source(source.source_id)
    assert after is not None
    assert after.last_run_at is not None
    assert after.error_count == 0
    assert after.last_error is None
    assert after.cursor_json == "{}"

