"""BoardRunEngine - Logic Layer for Board Delta Computation

Computes delta (new/removed/kept items) between two board snapshots,
producing a BoardBundle artifact.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from core.board.models import BoardSnapshotItem
from core.board.repository import BoardRepository
from core.runner.handlers import RunContext


class BoardRunEngine:
    """Logic layer for computing board delta between snapshots

    Pure computation engine with no I/O. All artifact storage is handled
    by BoardRunHandler.
    """

    def __init__(self, board_repo: BoardRepository) -> None:
        self.board_repo = board_repo

    def run(
        self,
        board_id: str,
        snapshot_id: str,
        baseline_snapshot_id: str | None = None,
        ctx: RunContext | None = None,
    ) -> dict[str, Any]:
        """Compute board delta and return BoardBundle dict

        Args:
            board_id: Board ID
            snapshot_id: Current snapshot ID
            baseline_snapshot_id: Previous snapshot ID (None for initial run)
            ctx: Optional RunContext for provenance

        Returns:
            BoardBundle dict with delta (new/removed/kept items)

        Raises:
            ValueError: If board or snapshot not found
        """
        # Validate board exists
        board = self.board_repo.get_board(board_id)
        if not board:
            raise ValueError(f"Board not found: {board_id}")

        # Fetch current snapshot and items
        current_snapshot = self.board_repo.get_snapshot(snapshot_id)
        if not current_snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        current_items = self.board_repo.list_snapshot_items(snapshot_id, limit=10000)

        # Handle no-baseline case (initial run)
        if baseline_snapshot_id is None:
            return self._create_bundle_no_baseline(
                board_id, snapshot_id, current_items
            )

        # Fetch baseline snapshot and items
        baseline_snapshot = self.board_repo.get_snapshot(baseline_snapshot_id)
        if not baseline_snapshot:
            raise ValueError(f"Baseline snapshot not found: {baseline_snapshot_id}")

        baseline_items = self.board_repo.list_snapshot_items(
            baseline_snapshot_id, limit=10000
        )

        # Compute delta
        delta = self._compute_delta(current_items, baseline_items)

        # Build BoardBundle
        bundle_id = f"bb_{uuid.uuid4().hex[:16]}"
        generated_at = datetime.utcnow().isoformat()

        return {
            "bundle_id": bundle_id,
            "board_id": board_id,
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
        current_items: list[BoardSnapshotItem],
        baseline_items: list[BoardSnapshotItem],
    ) -> dict[str, list[dict[str, Any]]]:
        """Compute delta using set operations on item_key

        Args:
            current_items: Items from current snapshot
            baseline_items: Items from baseline snapshot

        Returns:
            Dict with new_items, removed_items, kept_items
        """
        # Build item_key sets for comparison
        current_keys = {item.item_key for item in current_items}
        baseline_keys = {item.item_key for item in baseline_items}

        # Compute set operations
        new_keys = current_keys - baseline_keys
        removed_keys = baseline_keys - current_keys
        kept_keys = current_keys & baseline_keys

        # Build item lookup maps
        current_map = {item.item_key: item for item in current_items}
        baseline_map = {item.item_key: item for item in baseline_items}

        # Convert to sorted lists
        new_items = sorted(
            [self._item_to_dict(current_map[key]) for key in new_keys],
            key=lambda x: x["source_order"],
        )
        removed_items = sorted(
            [self._item_to_dict(baseline_map[key]) for key in removed_keys],
            key=lambda x: x["source_order"],
        )
        kept_items = sorted(
            [self._item_to_dict(current_map[key]) for key in kept_keys],
            key=lambda x: x["source_order"],
        )

        return {
            "new_items": new_items,
            "removed_items": removed_items,
            "kept_items": kept_items,
        }

    def _create_bundle_no_baseline(
        self,
        board_id: str,
        snapshot_id: str,
        current_items: list[BoardSnapshotItem],
    ) -> dict[str, Any]:
        """Create bundle for initial run (no baseline)

        All items are marked as "new".
        """
        bundle_id = f"bb_{uuid.uuid4().hex[:16]}"
        generated_at = datetime.utcnow().isoformat()

        new_items = sorted(
            [self._item_to_dict(item) for item in current_items],
            key=lambda x: x["source_order"],
        )

        return {
            "bundle_id": bundle_id,
            "board_id": board_id,
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

    def _item_to_dict(self, item: BoardSnapshotItem) -> dict[str, Any]:
        """Convert BoardSnapshotItem to dict with parsed meta

        Args:
            item: BoardSnapshotItem to convert

        Returns:
            Dict with all item fields, meta_json parsed to dict
        """
        meta = None
        if item.meta_json:
            try:
                meta = json.loads(item.meta_json)
            except json.JSONDecodeError:
                meta = None

        return {
            "item_key": item.item_key,
            "source_order": item.source_order,
            "title": item.title,
            "url": item.url,
            "meta": meta,
        }
