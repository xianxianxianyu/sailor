"""Tests for Research Repository - Snapshot Data Layer (P2.1)"""
import json
from datetime import datetime, timedelta

import pytest

from core.paper.repository import PaperRepository
from core.paper.models import PaperRecord
from core.storage.db import Database


@pytest.fixture
def paper_repo(tmp_path):
    """Create test paper repository"""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    repo = PaperRepository(db)
    return repo


def test_create_research_program(paper_repo):
    """Test creating research program"""
    program = paper_repo.upsert_research_program(
        name="ML Systems",
        description="Machine learning systems research",
        source_ids=["src_arxiv_cs_lg", "src_arxiv_cs_dc"],
        filters={"categories": ["cs.LG", "cs.DC"]},
        enabled=True,
    )

    assert program.program_id.startswith("rp_")
    assert program.name == "ML Systems"
    assert json.loads(program.source_ids) == ["src_arxiv_cs_lg", "src_arxiv_cs_dc"]
    assert json.loads(program.filters_json) == {"categories": ["cs.LG", "cs.DC"]}
    assert program.enabled is True


def test_get_research_program(paper_repo):
    """Test retrieving research program"""
    program = paper_repo.upsert_research_program(
        name="NLP Research",
        description="Natural language processing",
        source_ids=["src_arxiv_cs_cl"],
        filters={"categories": ["cs.CL"]},
    )

    retrieved = paper_repo.get_research_program(program.program_id)
    assert retrieved is not None
    assert retrieved.program_id == program.program_id
    assert retrieved.name == "NLP Research"


def test_list_research_programs(paper_repo):
    """Test listing research programs"""
    paper_repo.upsert_research_program(
        name="Program 1",
        description="First program",
        source_ids=["src1"],
    )
    paper_repo.upsert_research_program(
        name="Program 2",
        description="Second program",
        source_ids=["src2"],
        enabled=False,
    )

    # List all
    all_programs = paper_repo.list_research_programs()
    assert len(all_programs) == 2

    # List enabled only
    enabled_programs = paper_repo.list_research_programs(enabled_only=True)
    assert len(enabled_programs) == 1
    assert enabled_programs[0].name == "Program 1"


def test_create_research_snapshot(paper_repo):
    """Test creating research snapshot"""
    # Create program first
    program = paper_repo.upsert_research_program(
        name="Test Program",
        description="Test",
        source_ids=["src1"],
    )

    # Create snapshot
    captured_at = datetime.utcnow()
    snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since="2024-01-01T00:00:00",
        window_until="2024-12-31T23:59:59",
        captured_at=captured_at,
    )

    assert snapshot_id.startswith("rsnap_")

    # Verify snapshot
    snapshot = paper_repo.get_research_snapshot(snapshot_id)
    assert snapshot is not None
    assert snapshot.program_id == program.program_id
    assert snapshot.window_since == "2024-01-01T00:00:00"
    assert snapshot.paper_count == 0  # No items added yet


def test_add_research_snapshot_items(paper_repo):
    """Test adding papers to snapshot"""
    # Create program and snapshot
    program = paper_repo.upsert_research_program(
        name="Test Program",
        description="Test",
        source_ids=["src1"],
    )
    snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )

    # Create test papers
    paper1_id = paper_repo.upsert_paper(
        PaperRecord(
            canonical_id="arxiv:2401.00001",
            canonical_url="https://arxiv.org/abs/2401.00001",
            title="Paper 1",
            item_key="2401.00001",
            abstract="Abstract 1",
        )
    )
    paper2_id = paper_repo.upsert_paper(
        PaperRecord(
            canonical_id="arxiv:2401.00002",
            canonical_url="https://arxiv.org/abs/2401.00002",
            title="Paper 2",
            item_key="2401.00002",
            abstract="Abstract 2",
        )
    )

    # Add papers to snapshot
    paper_repo.add_research_snapshot_items(
        snapshot_id=snapshot_id,
        paper_ids=[paper1_id, paper2_id],
    )

    # Verify items
    items = paper_repo.list_research_snapshot_items(snapshot_id)
    assert len(items) == 2
    assert items[0] == (paper1_id, 1)
    assert items[1] == (paper2_id, 2)

    # Verify paper_count updated
    snapshot = paper_repo.get_research_snapshot(snapshot_id)
    assert snapshot.paper_count == 2


def test_list_research_snapshots(paper_repo):
    """Test listing snapshots for a program"""
    program = paper_repo.upsert_research_program(
        name="Test Program",
        description="Test",
        source_ids=["src1"],
    )

    # Create multiple snapshots
    now = datetime.utcnow()
    snapshot1_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=now - timedelta(days=2),
    )
    snapshot2_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=now - timedelta(days=1),
    )
    snapshot3_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=now,
    )

    # List snapshots (should be ordered by captured_at DESC)
    snapshots = paper_repo.list_research_snapshots(program.program_id)
    assert len(snapshots) == 3
    assert snapshots[0].snapshot_id == snapshot3_id  # Most recent first
    assert snapshots[1].snapshot_id == snapshot2_id
    assert snapshots[2].snapshot_id == snapshot1_id


def test_get_latest_research_snapshot(paper_repo):
    """Test getting latest snapshot"""
    program = paper_repo.upsert_research_program(
        name="Test Program",
        description="Test",
        source_ids=["src1"],
    )

    # Create snapshots
    now = datetime.utcnow()
    paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=now - timedelta(days=1),
    )
    latest_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=now,
    )

    # Get latest
    latest = paper_repo.get_latest_research_snapshot(program.program_id)
    assert latest is not None
    assert latest.snapshot_id == latest_id


def test_delete_research_program(paper_repo):
    """Test deleting research program"""
    program = paper_repo.upsert_research_program(
        name="To Delete",
        description="Test",
        source_ids=["src1"],
    )

    # Delete
    success = paper_repo.delete_research_program(program.program_id)
    assert success is True

    # Verify deleted
    retrieved = paper_repo.get_research_program(program.program_id)
    assert retrieved is None


def test_program_id_deterministic(paper_repo):
    """Test that program IDs are deterministic"""
    program1 = paper_repo.upsert_research_program(
        name="Same Name",
        description="First",
        source_ids=["src1"],
    )

    # Upsert with same name should return same ID
    program2 = paper_repo.upsert_research_program(
        name="Same Name",
        description="Updated",
        source_ids=["src2"],
    )

    assert program1.program_id == program2.program_id
    assert program2.description == "Updated"  # Should be updated


def test_snapshot_id_deterministic(paper_repo):
    """Test that snapshot IDs are deterministic"""
    program = paper_repo.upsert_research_program(
        name="Test",
        description="Test",
        source_ids=["src1"],
    )

    captured_at = datetime(2024, 1, 1, 12, 0, 0)

    # Create snapshot
    snapshot1_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=captured_at,
    )

    # Try to create again with same params (should fail due to PK constraint)
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        paper_repo.create_research_snapshot(
            program_id=program.program_id,
            window_since=None,
            window_until=None,
            captured_at=captured_at,
        )


def test_empty_filters(paper_repo):
    """Test creating program with no filters"""
    program = paper_repo.upsert_research_program(
        name="No Filters",
        description="Test",
        source_ids=["src1"],
        filters=None,
    )

    assert json.loads(program.filters_json) == {}


def test_multiple_source_ids(paper_repo):
    """Test program with multiple source IDs"""
    program = paper_repo.upsert_research_program(
        name="Multi Source",
        description="Test",
        source_ids=["src1", "src2", "src3"],
    )

    assert json.loads(program.source_ids) == ["src1", "src2", "src3"]


def test_snapshot_with_no_time_window(paper_repo):
    """Test snapshot without time window constraints"""
    program = paper_repo.upsert_research_program(
        name="Test",
        description="Test",
        source_ids=["src1"],
    )

    snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )

    snapshot = paper_repo.get_research_snapshot(snapshot_id)
    assert snapshot.window_since is None
    assert snapshot.window_until is None


def test_list_snapshot_items_pagination(paper_repo):
    """Test pagination of snapshot items"""
    program = paper_repo.upsert_research_program(
        name="Test",
        description="Test",
        source_ids=["src1"],
    )
    snapshot_id = paper_repo.create_research_snapshot(
        program_id=program.program_id,
        window_since=None,
        window_until=None,
        captured_at=datetime.utcnow(),
    )

    # Create 5 papers
    paper_ids = []
    for i in range(5):
        paper_id = paper_repo.upsert_paper(
            PaperRecord(
                canonical_id=f"arxiv:2401.0000{i}",
                canonical_url=f"https://arxiv.org/abs/2401.0000{i}",
                title=f"Paper {i}",
                item_key=f"2401.0000{i}",
            )
        )
        paper_ids.append(paper_id)

    paper_repo.add_research_snapshot_items(snapshot_id, paper_ids)

    # Test pagination
    page1 = paper_repo.list_research_snapshot_items(snapshot_id, limit=2, offset=0)
    assert len(page1) == 2
    assert page1[0][1] == 1  # First item has order 1
    assert page1[1][1] == 2

    page2 = paper_repo.list_research_snapshot_items(snapshot_id, limit=2, offset=2)
    assert len(page2) == 2
    assert page2[0][1] == 3
    assert page2[1][1] == 4
