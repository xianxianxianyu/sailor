"""Artifact Data Models

Unified artifact envelope for all Follow system outputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Artifact:
    """Unified artifact envelope for all Follow system outputs

    Supports multiple artifact kinds:
    - issue_snapshot: IssueSnapshot from IssueComposerEngine
    - research_bundle: ResearchBundle from ResearchRunEngine
    - board_bundle: BoardBundle from BoardRunEngine
    - board_snapshot: BoardSnapshot from BoardRunEngine
    """
    artifact_id: str
    kind: str  # issue_snapshot|research_bundle|board_bundle|board_snapshot
    schema_version: str
    content: dict  # actual artifact content
    content_ref: str | None = None  # large file reference (optional)
    input_refs: dict | None = None  # input references: {snapshot_ids, bundle_ids, job_ids}
    producer: dict | None = None  # {engine, engine_version, code_ref}
    job_id: str | None = None
    created_at: datetime | None = None
    metadata: dict | None = None
