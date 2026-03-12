"""Artifact Repository

Storage layer for all Follow system artifacts.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from core.storage.db import Database
from .models import Artifact

logger = logging.getLogger(__name__)


class ArtifactRepository:
    """Unified artifact storage for all Follow system outputs"""

    def __init__(self, db: Database):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create artifacts table and indexes"""
        with self.db.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    content_ref TEXT NULL,
                    input_refs_json TEXT NULL,
                    producer_engine TEXT NOT NULL,
                    producer_version TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_artifacts_kind
                ON artifacts(kind)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_artifacts_job_id
                ON artifacts(job_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_artifacts_created_at
                ON artifacts(created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_artifacts_kind_created
                ON artifacts(kind, created_at DESC)
            """)

    def put(
        self,
        kind: str,
        schema_version: str,
        content: dict,
        producer_engine: str,
        producer_version: str,
        job_id: str,
        content_ref: str | None = None,
        input_refs: dict | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Store an artifact

        Args:
            kind: Artifact kind (issue_snapshot|research_bundle|board_bundle|board_snapshot)
            schema_version: Schema version (v1, v2, ...)
            content: Artifact content as dict
            producer_engine: Engine name that produced this artifact
            producer_version: Engine version
            job_id: Associated job ID
            content_ref: Optional file reference for large content
            input_refs: Optional input references dict
            metadata: Optional extended metadata

        Returns:
            artifact_id: Generated artifact ID (art_{uuid})
        """
        artifact_id = self._generate_artifact_id()
        created_at = datetime.utcnow().isoformat()

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, kind, schema_version, content_json, content_ref,
                    input_refs_json, producer_engine, producer_version, job_id,
                    created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    kind,
                    schema_version,
                    json.dumps(content),
                    content_ref,
                    json.dumps(input_refs) if input_refs else None,
                    producer_engine,
                    producer_version,
                    job_id,
                    created_at,
                    json.dumps(metadata) if metadata else None,
                ),
            )

        return artifact_id

    def get(self, artifact_id: str) -> Artifact | None:
        """Retrieve artifact by ID

        Args:
            artifact_id: Artifact ID to retrieve

        Returns:
            Artifact object or None if not found
        """
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            return self._row_to_artifact(row) if row else None

    def list(
        self,
        kind: str | None = None,
        job_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Artifact]:
        """List artifacts with filters

        Args:
            kind: Filter by artifact kind
            job_id: Filter by job ID
            since: Filter by created_at >= since
            until: Filter by created_at < until
            limit: Maximum number of artifacts to return
            offset: Number of artifacts to skip

        Returns:
            List of Artifact objects ordered by created_at DESC
        """
        with self.db.connect() as conn:
            query = "SELECT * FROM artifacts WHERE 1=1"
            params: list[Any] = []

            if kind:
                query += " AND kind = ?"
                params.append(kind)

            if job_id:
                query += " AND job_id = ?"
                params.append(job_id)

            if since:
                query += " AND created_at >= ?"
                params.append(since.isoformat())

            if until:
                query += " AND created_at < ?"
                params.append(until.isoformat())

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_artifact(row) for row in rows]

    def find_latest_by_kind(self, kind: str) -> Artifact | None:
        """Find the latest artifact of a specific kind

        Args:
            kind: Artifact kind to search for

        Returns:
            Latest Artifact of the specified kind or None
        """
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM artifacts
                WHERE kind = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (kind,),
            ).fetchone()
            return self._row_to_artifact(row) if row else None

    # ========== Helper Methods ==========

    def _generate_artifact_id(self) -> str:
        """Generate unique artifact ID"""
        return f"art_{uuid.uuid4().hex[:16]}"

    def _row_to_artifact(self, row: Any) -> Artifact:
        """Convert DB row to Artifact"""
        # Build producer dict from engine fields
        producer = {
            "engine": row[6],  # producer_engine
            "engine_version": row[7],  # producer_version
        }

        return Artifact(
            artifact_id=row[0],
            kind=row[1],
            schema_version=row[2],
            content=json.loads(row[3]),
            content_ref=row[4],
            input_refs=json.loads(row[5]) if row[5] else None,
            producer=producer,
            job_id=row[8],
            created_at=datetime.fromisoformat(row[9]),
            metadata=json.loads(row[10]) if row[10] else None,
        )
