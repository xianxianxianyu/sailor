"""P1-4 paper engine: compat + consistency guard tests."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from core.paper.models import PaperRecord
from core.paper.repository import PaperRepository
from core.storage.db import Database


@pytest.fixture()
def paper_repo(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    return PaperRepository(db)


def test_upsert_paper_writes_raw_meta_json(paper_repo: PaperRepository):
    rec = PaperRecord(
        canonical_id="arxiv:2401.00001",
        canonical_url="https://arxiv.org/abs/2401.00001",
        title="Paper 1",
        item_key="2401.00001",
        abstract="abs",
        published_at=datetime.utcnow(),
        authors=["Alice", "Bob"],
        external_ids={"arxiv_id": "2401.00001"},
        raw_meta={"source": "arxiv", "raw": {"k": "v"}},
    )
    paper_id = paper_repo.upsert_paper(rec)
    stored = paper_repo.get_paper(paper_id)
    assert stored is not None
    assert json.loads(stored.raw_meta_json or "{}") == {"source": "arxiv", "raw": {"k": "v"}}

    rec2 = PaperRecord(
        canonical_id=rec.canonical_id,
        canonical_url=rec.canonical_url,
        title=rec.title,
        item_key=rec.item_key,
        raw_meta={"source": "arxiv", "raw": {"k": "v2"}},
    )
    paper_repo.upsert_paper(rec2)
    stored2 = paper_repo.get_paper(paper_id)
    assert stored2 is not None
    assert json.loads(stored2.raw_meta_json or "{}") == {"source": "arxiv", "raw": {"k": "v2"}}


def test_list_papers_orders_null_published_at_last(paper_repo: PaperRepository):
    paper_repo.upsert_paper(PaperRecord(
        canonical_id="arxiv:null",
        canonical_url="https://arxiv.org/abs/null",
        title="Null Published",
        item_key="null",
        published_at=None,
    ))
    paper_repo.upsert_paper(PaperRecord(
        canonical_id="arxiv:dated",
        canonical_url="https://arxiv.org/abs/dated",
        title="Has Published",
        item_key="dated",
        published_at=datetime.utcnow(),
    ))

    papers = paper_repo.list_papers(limit=10)
    assert papers[0].canonical_id == "arxiv:dated"


def test_record_source_error_increments_error_count_atomically(paper_repo: PaperRepository):
    source = paper_repo.upsert_source(
        source_id=None,
        platform="arxiv",
        endpoint="cat:cs.AI",
        name="Test Source",
        config_json="{}",
        enabled=True,
    )

    paper_repo.record_source_error(source.source_id, "e1")
    paper_repo.record_source_error(source.source_id, "e2")

    updated = paper_repo.get_source(source.source_id)
    assert updated is not None
    assert updated.error_count == 2
    assert updated.last_error == "e2"

