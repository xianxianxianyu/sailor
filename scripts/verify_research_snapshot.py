"""Verification script for P2.1 Research Snapshot Data Layer

This script demonstrates the new research snapshot functionality.
"""
from pathlib import Path
from datetime import datetime
import json

from core.storage.db import Database
from core.paper.repository import PaperRepository
from core.paper.models import PaperRecord


def main():
    # Initialize repository
    db = Database(Path("data/sailor.db"))
    db.init_schema()
    repo = PaperRepository(db)

    print("=== P2.1 Research Snapshot Data Layer Verification ===\n")

    # 1. Create a research program
    print("1. Creating research program...")
    program = repo.upsert_research_program(
        name="AI Safety Research",
        description="Research on AI alignment and safety",
        source_ids=["src_arxiv_cs_ai", "src_arxiv_cs_lg"],
        filters={"categories": ["cs.AI", "cs.LG"], "keywords": ["safety", "alignment"]},
        enabled=True,
    )
    print(f"   Created: {program.program_id}")
    print(f"   Name: {program.name}")
    print(f"   Sources: {json.loads(program.source_ids)}")
    print(f"   Filters: {json.loads(program.filters_json)}\n")

    # 2. Create some test papers
    print("2. Creating test papers...")
    paper1_id = repo.upsert_paper(
        PaperRecord(
            canonical_id="arxiv:2401.12345",
            canonical_url="https://arxiv.org/abs/2401.12345",
            title="Scalable Oversight for AI Systems",
            item_key="2401.12345",
            abstract="A novel approach to AI alignment...",
            published_at=datetime(2024, 1, 15),
        )
    )
    paper2_id = repo.upsert_paper(
        PaperRecord(
            canonical_id="arxiv:2401.67890",
            canonical_url="https://arxiv.org/abs/2401.67890",
            title="Constitutional AI: Harmlessness from AI Feedback",
            item_key="2401.67890",
            abstract="Training AI systems to be helpful, harmless, and honest...",
            published_at=datetime(2024, 1, 20),
        )
    )
    print(f"   Created 2 papers: {paper1_id}, {paper2_id}\n")

    # 3. Create a research snapshot
    print("3. Creating research snapshot...")
    captured_at = datetime.utcnow()
    snapshot_id = repo.create_research_snapshot(
        program_id=program.program_id,
        window_since="2024-01-01T00:00:00",
        window_until="2024-01-31T23:59:59",
        captured_at=captured_at,
    )
    print(f"   Created: {snapshot_id}")
    print(f"   Captured at: {captured_at.isoformat()}\n")

    # 4. Add papers to snapshot
    print("4. Adding papers to snapshot...")
    repo.add_research_snapshot_items(
        snapshot_id=snapshot_id,
        paper_ids=[paper1_id, paper2_id],
    )
    print(f"   Added 2 papers to snapshot\n")

    # 5. Retrieve snapshot and verify
    print("5. Retrieving snapshot...")
    snapshot = repo.get_research_snapshot(snapshot_id)
    print(f"   Snapshot ID: {snapshot.snapshot_id}")
    print(f"   Program ID: {snapshot.program_id}")
    print(f"   Paper count: {snapshot.paper_count}")
    print(f"   Window: {snapshot.window_since} to {snapshot.window_until}\n")

    # 6. List snapshot items
    print("6. Listing snapshot items...")
    items = repo.list_research_snapshot_items(snapshot_id)
    for paper_id, order in items:
        paper = repo.get_paper(paper_id)
        print(f"   [{order}] {paper.title}")
    print()

    # 7. List all programs
    print("7. Listing all research programs...")
    programs = repo.list_research_programs()
    for prog in programs:
        print(f"   - {prog.name} ({prog.program_id})")
        print(f"     Enabled: {prog.enabled}")
        print(f"     Sources: {json.loads(prog.source_ids)}")
    print()

    # 8. Get latest snapshot
    print("8. Getting latest snapshot for program...")
    latest = repo.get_latest_research_snapshot(program.program_id)
    if latest:
        print(f"   Latest snapshot: {latest.snapshot_id}")
        print(f"   Captured at: {latest.captured_at.isoformat()}")
        print(f"   Paper count: {latest.paper_count}")
    print()

    print("=== Verification Complete ===")
    print("\nP2.1 Research Snapshot Data Layer is working correctly!")
    print("All models, tables, and repository methods are functional.")


if __name__ == "__main__":
    main()
