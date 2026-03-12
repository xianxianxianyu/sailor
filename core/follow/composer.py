"""IssueComposerEngine - Logic Layer for Issue Composition

Composes IssueSnapshot artifacts from ResearchBundle and BoardBundle inputs.
Pure composition logic with no I/O dependencies.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.runner.handlers import RunContext
from .models import FollowSpec


class IssueComposerEngine:
    """Logic layer for composing IssueSnapshot from bundles

    Pure composition engine with no dependencies. Takes bundle dicts directly
    and combines them into a unified IssueSnapshot artifact.
    """

    def __init__(self) -> None:
        # No dependencies - pure composition logic
        pass

    def compose(
        self,
        follow_spec: FollowSpec,
        window: dict[str, str],
        research_bundle: dict[str, Any] | None,
        board_bundles: list[dict[str, Any]],
        ctx: RunContext | None = None,
    ) -> dict[str, Any]:
        """Compose IssueSnapshot from bundles

        Args:
            follow_spec: Follow configuration
            window: Time window {"since": str, "until": str}
            research_bundle: ResearchBundle dict (optional)
            board_bundles: List of BoardBundle dicts
            ctx: Optional RunContext for provenance

        Returns:
            IssueSnapshot dict with sections and metadata
        """
        # Build sections from bundles
        sections = []

        # Add board sections first (boards before research)
        for bundle in board_bundles:
            section = self._build_board_section(bundle)
            sections.append(section)

        # Add research section if present
        if research_bundle:
            section = self._build_research_section(research_bundle)
            sections.append(section)

        # Build input refs
        input_refs: dict[str, Any] = {
            "research_bundle_id": research_bundle["bundle_id"] if research_bundle else None,
            "board_bundle_ids": [b["bundle_id"] for b in board_bundles],
        }

        # Generate issue ID and metadata
        issue_id = f"iss_{uuid.uuid4().hex[:16]}"
        generated_at = datetime.utcnow().isoformat()
        total_items = sum(len(s["items"]) for s in sections)

        return {
            "issue_id": issue_id,
            "follow_id": follow_spec.follow_id,
            "window": window,
            "ordering_policy": "v1:default",
            "sections": sections,
            "input_refs": input_refs,
            "metadata": {
                "engine_version": "v1",
                "generated_at": generated_at,
                "total_items": total_items,
                "section_count": len(sections),
            },
        }

    def _build_board_section(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Build section from BoardBundle

        Board sections order items as: new_items first (by source_order),
        then kept_items (by source_order).

        Args:
            bundle: BoardBundle dict with delta structure

        Returns:
            Section dict with ordered items
        """
        delta = bundle["delta"]
        new_items = delta.get("new_items", [])
        kept_items = delta.get("kept_items", [])

        # Combine: new_items first, then kept_items
        # Both are already sorted by source_order from BoardRunEngine
        items = new_items + kept_items

        return {
            "section_id": f"board.{bundle['board_id']}",
            "title": f"Board: {bundle['board_id']}",
            "items": items,
            "metadata": {
                "new_count": len(new_items),
                "kept_count": len(kept_items),
            },
        }

    def _build_research_section(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Build section from ResearchBundle

        Research sections combine new_items + kept_items and sort by
        published_at DESC, with item_key as tiebreaker.

        Args:
            bundle: ResearchBundle dict with delta structure

        Returns:
            Section dict with ordered items
        """
        delta = bundle["delta"]
        new_items = delta.get("new_items", [])
        kept_items = delta.get("kept_items", [])

        # Combine all items
        all_items = new_items + kept_items

        # Sort by published_at DESC, item_key as tiebreaker
        # published_at is in ISO format, so string comparison works
        sorted_items = sorted(
            all_items,
            key=lambda x: (
                x.get("published_at", ""),  # Primary: published_at DESC
                x.get("item_key", ""),      # Tiebreaker: item_key
            ),
            reverse=True,  # DESC order
        )

        return {
            "section_id": f"research.{bundle['program_id']}",
            "title": f"Research: {bundle['program_id']}",
            "items": sorted_items,
            "metadata": {
                "new_count": len(new_items),
                "kept_count": len(kept_items),
            },
        }
