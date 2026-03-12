"""P1-1 contract tests: enabled filtering is tri-state.

Tri-state semantics:
- param omitted: no filtering
- enabled=true: only enabled records
- enabled=false: only disabled records
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _create_project_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "seed_entries.json").write_text("[]", encoding="utf-8")
    (tmp_path / "1.md").write_text("<opml/>", encoding="utf-8")


@pytest.fixture()
def api_client(tmp_path: Path):
    test_db_path = tmp_path / "data" / "sailor.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)

    old_db_path = os.environ.get("SAILOR_DB_PATH")
    os.environ["SAILOR_DB_PATH"] = str(test_db_path)

    container = None
    try:
        _create_project_files(tmp_path)

        # Force reimport to avoid leaking module-level routers between tests.
        for mod in [m for m in sys.modules.keys() if m.startswith("backend.app")]:
            del sys.modules[mod]

        from backend.app.container import build_container
        from backend.app.routers.boards import mount_board_routes
        from backend.app.routers.follows import mount_follow_routes
        from backend.app.routers.research_programs import mount_research_program_routes

        container = build_container(tmp_path)

        app = FastAPI(title="Sailor Test", version="0.1.0")
        for r in mount_board_routes(container):
            app.include_router(r)
        app.include_router(mount_follow_routes(container))
        app.include_router(mount_research_program_routes(container))

        client = TestClient(app)
        yield client, container
    finally:
        if container is not None and getattr(container, "scheduler", None):
            try:
                container.scheduler.stop()
            except Exception:
                pass

        if old_db_path is not None:
            os.environ["SAILOR_DB_PATH"] = old_db_path
        else:
            os.environ.pop("SAILOR_DB_PATH", None)


def test_enabled_filter_tristate_across_routers(api_client):
    client, container = api_client
    suffix = uuid.uuid4().hex[:8]

    b_enabled = container.board_repo.upsert_board(
        provider="github",
        kind="trending",
        name=f"b_en_{suffix}",
        config_json="{}",
        enabled=True,
    )
    b_disabled = container.board_repo.upsert_board(
        provider="github",
        kind="trending",
        name=f"b_dis_{suffix}",
        config_json="{}",
        enabled=False,
    )

    f_enabled = container.follow_repo.upsert_follow(
        name=f"f_en_{suffix}",
        description=None,
        board_ids=[],
        research_program_ids=[],
        enabled=True,
    )
    f_disabled = container.follow_repo.upsert_follow(
        name=f"f_dis_{suffix}",
        description=None,
        board_ids=[],
        research_program_ids=[],
        enabled=False,
    )

    p_enabled = container.paper_repo.upsert_research_program(
        name=f"p_en_{suffix}",
        description=None,
        source_ids=[],
        filters=None,
        enabled=True,
    )
    p_disabled = container.paper_repo.upsert_research_program(
        name=f"p_dis_{suffix}",
        description=None,
        source_ids=[],
        filters=None,
        enabled=False,
    )

    # Boards
    all_board_ids = {b["board_id"] for b in client.get("/boards").json()}
    assert {b_enabled.board_id, b_disabled.board_id}.issubset(all_board_ids)

    enabled_board_ids = {b["board_id"] for b in client.get("/boards?enabled=true").json()}
    assert enabled_board_ids == {b_enabled.board_id}

    disabled_board_ids = {b["board_id"] for b in client.get("/boards?enabled=false").json()}
    assert disabled_board_ids == {b_disabled.board_id}

    # Follows
    all_follow_ids = {f["follow_id"] for f in client.get("/follows").json()}
    assert {f_enabled.follow_id, f_disabled.follow_id}.issubset(all_follow_ids)

    enabled_follow_ids = {f["follow_id"] for f in client.get("/follows?enabled=true").json()}
    assert enabled_follow_ids == {f_enabled.follow_id}

    disabled_follow_ids = {f["follow_id"] for f in client.get("/follows?enabled=false").json()}
    assert disabled_follow_ids == {f_disabled.follow_id}

    # Research programs
    all_program_ids = {p["program_id"] for p in client.get("/research-programs").json()}
    assert {p_enabled.program_id, p_disabled.program_id}.issubset(all_program_ids)

    enabled_program_ids = {p["program_id"] for p in client.get("/research-programs?enabled=true").json()}
    assert enabled_program_ids == {p_enabled.program_id}

    disabled_program_ids = {p["program_id"] for p in client.get("/research-programs?enabled=false").json()}
    assert disabled_program_ids == {p_disabled.program_id}
