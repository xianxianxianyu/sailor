"""P1-2 contract tests: PATCH keeps program_id stable across rename."""

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

        for mod in [m for m in sys.modules.keys() if m.startswith("backend.app")]:
            del sys.modules[mod]

        from backend.app.container import build_container
        from backend.app.routers.research_programs import mount_research_program_routes

        container = build_container(tmp_path)

        app = FastAPI(title="Sailor Test", version="0.1.0")
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


def test_patch_rename_does_not_change_program_id(api_client):
    client, container = api_client

    suffix = uuid.uuid4().hex[:8]
    program = container.paper_repo.upsert_research_program(
        name=f"Old Name {suffix}",
        description="desc",
        source_ids=["src1"],
        filters={"keywords": ["x"]},
        enabled=True,
    )

    new_name = f"New Name {suffix}"
    resp = client.patch(f"/research-programs/{program.program_id}", json={"name": new_name})
    assert resp.status_code == 200
    data = resp.json()

    assert data["program_id"] == program.program_id
    assert data["name"] == new_name

    programs = container.paper_repo.list_research_programs()
    assert len(programs) == 1
    assert programs[0].program_id == program.program_id
    assert programs[0].name == new_name
