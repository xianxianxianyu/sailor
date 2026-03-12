"""ResearchRunEngine - Logic Layer for Research Delta Computation

Computes delta (new/removed/kept papers) between two research snapshots,
producing a ResearchBundle artifact.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.paper.models import paper_to_research_item
from core.paper.repository import PaperRepository
from core.runner.handlers import RunContext


class ResearchRunEngine:
    """Logic layer for computing research delta between snapshots

    Pure computation engine with no I/O. All artifact storage is handled
    by ResearchRunHandler.
    """

    def __init__(self, paper_repo: PaperRepository) -> None:
        self.paper_repo = paper_repo

    def run(
        self,
        program_id: str,
        snapshot_id: str,
        baseline_snapshot_id: str | None = None,
        ctx: RunContext | None = None,
    ) -> dict[str, Any]:
        """Compute research delta and return ResearchBundle dict

        Args:
            program_id: Research program ID
            snapshot_id: Current snapshot ID
            baseline_snapshot_id: Previous snapshot ID (None for initial run)
            ctx: Optional RunContext for provenance

        Returns:
            ResearchBundle dict with delta (new/removed/kept items)

        Raises:
            ValueError: If program or snapshot not found
        """
        # Validate program exists and is enabled
        program = self.paper_repo.get_research_program(program_id)
        if not program:
            raise ValueError(f"Research program not found: {program_id}")
        if not program.enabled:
            raise ValueError(f"Research program is disabled: {program_id}")

        # Fetch current snapshot and items
        current_snapshot = self.paper_repo.get_research_snapshot(snapshot_id)
        if not current_snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        current_items = self.paper_repo.list_research_snapshot_items(
            snapshot_id, limit=10000
        )

        # Handle no-baseline case (initial run)
        if baseline_snapshot_id is None:
            return self._create_bundle_no_baseline(
                program_id, snapshot_id, current_items
            )

        # Fetch baseline snapshot and items
        baseline_snapshot = self.paper_repo.get_research_snapshot(baseline_snapshot_id)
        if not baseline_snapshot:
            raise ValueError(f"Baseline snapshot not found: {baseline_snapshot_id}")

        baseline_items = self.paper_repo.list_research_snapshot_items(
            baseline_snapshot_id, limit=10000
        )

        # Compute delta
        delta = self._compute_delta(current_items, baseline_items)

        # Build ResearchBundle
        bundle_id = f"rb_{uuid.uuid4().hex[:16]}"
        generated_at = datetime.utcnow().isoformat()

        return {
            "bundle_id": bundle_id,
            "program_id": program_id,
            "snapshot_id": snapshot_id,
            "baseline_snapshot_id": baseline_snapshot_id,
            "delta": delta,
            "metadata": {
                "engine_version": "v1",
                "generated_at": generated_at,
                "new_count": len(delta["new_items"]),
                "removed_count": len(delta["removed_items"]),
                "kept_count": len(delta["kept_items"]),
            },
        }

    def _compute_delta(
        self,
        current_items: list[tuple[str, int]],
        baseline_items: list[tuple[str, int]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Compute delta using set operations on paper_id

        Args:
            current_items: (paper_id, source_order) tuples from current snapshot
            baseline_items: (paper_id, source_order) tuples from baseline snapshot

        Returns:
            Dict with new_items, removed_items, kept_items
        """
        # Build paper_id sets for comparison
        current_ids = {paper_id for paper_id, _ in current_items}
        baseline_ids = {paper_id for paper_id, _ in baseline_items}

        # Compute set operations
        new_ids = current_ids - baseline_ids
        removed_ids = baseline_ids - current_ids
        kept_ids = current_ids & baseline_ids

        # Build lookup maps
        current_map = {paper_id: source_order for paper_id, source_order in current_items}
        baseline_map = {paper_id: source_order for paper_id, source_order in baseline_items}

        # Fetch Paper objects and convert to research items
        new_items = self._fetch_and_convert_papers(new_ids, current_map)
        removed_items = self._fetch_and_convert_papers(removed_ids, baseline_map)
        kept_items = self._fetch_and_convert_papers(kept_ids, current_map)

        # Sort by source_order
        new_items.sort(key=lambda x: x.get("source_order", 0))
        removed_items.sort(key=lambda x: x.get("source_order", 0))
        kept_items.sort(key=lambda x: x.get("source_order", 0))

        return {
            "new_items": new_items,
            "removed_items": removed_items,
            "kept_items": kept_items,
        }

    def _create_bundle_no_baseline(
        self,
        program_id: str,
        snapshot_id: str,
        current_items: list[tuple[str, int]],
    ) -> dict[str, Any]:
        """Create bundle for initial run (no baseline)

        All items are marked as "new".
        """
        bundle_id = f"rb_{uuid.uuid4().hex[:16]}"
        generated_at = datetime.utcnow().isoformat()

        # Build lookup map
        current_map = {paper_id: source_order for paper_id, source_order in current_items}
        paper_ids = {paper_id for paper_id, _ in current_items}

        # Fetch and convert papers
        new_items = self._fetch_and_convert_papers(paper_ids, current_map)
        new_items.sort(key=lambda x: x.get("source_order", 0))

        return {
            "bundle_id": bundle_id,
            "program_id": program_id,
            "snapshot_id": snapshot_id,
            "baseline_snapshot_id": None,
            "delta": {
                "new_items": new_items,
                "removed_items": [],
                "kept_items": [],
            },
            "metadata": {
                "engine_version": "v1",
                "generated_at": generated_at,
                "new_count": len(new_items),
                "removed_count": 0,
                "kept_count": 0,
            },
        }

    def _fetch_and_convert_papers(
        self,
        paper_ids: set[str],
        order_map: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Fetch Paper objects and convert to research item format

        Args:
            paper_ids: Set of paper IDs to fetch
            order_map: Map of paper_id -> source_order

        Returns:
            List of research item dicts with source_order added
        """
        items = []
        for paper_id in paper_ids:
            paper = self.paper_repo.get_paper(paper_id)
            if paper:
                item = paper_to_research_item(paper)
                item["source_order"] = order_map.get(paper_id, 0)
                items.append(item)
        return items
