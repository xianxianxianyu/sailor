"""Paper Engine Repository

Paper Engine 数据层存储实现（模块 1-4）
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from core.storage import Database
from .models import (
    Paper,
    PaperRecord,
    PaperRun,
    PaperSource,
    PaperSourceItem,
    ResearchProgram,
    ResearchSnapshot,
    ResearchSnapshotItem,
)

logger = logging.getLogger(__name__)


class PaperRepository:
    """Paper Engine 统一存储层"""

    def __init__(self, db: Database):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """创建 Paper Engine 所需的表"""
        with self.db.connect() as conn:
            # 模块 1: paper_sources
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_sources (
                    source_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    name TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    cursor_json TEXT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    schedule_minutes INTEGER NULL,
                    last_run_at TEXT NULL,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(platform, endpoint)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_paper_sources_enabled_platform
                ON paper_sources(enabled, platform)
            """)

            # 模块 2: papers
            conn.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    paper_id TEXT PRIMARY KEY,
                    canonical_id TEXT NOT NULL UNIQUE,
                    canonical_url TEXT NULL UNIQUE,
                    title TEXT NOT NULL,
                    abstract TEXT NULL,
                    published_at TEXT NULL,
                    authors_json TEXT NULL,
                    venue TEXT NULL,
                    doi TEXT NULL,
                    pdf_url TEXT NULL,
                    external_ids_json TEXT NULL,
                    raw_meta_json TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_papers_published_at
                ON papers(published_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_papers_venue
                ON papers(venue)
            """)

            # 模块 3: paper_source_items
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_source_items (
                    source_id TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    paper_id TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY(source_id, item_key),
                    FOREIGN KEY(paper_id) REFERENCES papers(paper_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_paper_source_items_paper_id
                ON paper_source_items(paper_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_paper_source_items_source_last_seen
                ON paper_source_items(source_id, last_seen_at)
            """)

            # 模块 4: paper_runs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_runs (
                    run_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    job_id TEXT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NULL,
                    fetched_count INTEGER NOT NULL DEFAULT 0,
                    processed_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NULL,
                    metrics_json TEXT NULL,
                    cursor_before_json TEXT NULL,
                    cursor_after_json TEXT NULL,
                    FOREIGN KEY(source_id) REFERENCES paper_sources(source_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_paper_runs_source_started
                ON paper_runs(source_id, started_at)
            """)

            # Research Programs (P2.1)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_programs (
                    program_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NULL,
                    source_ids TEXT NOT NULL,
                    filters_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(name)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_research_programs_enabled
                ON research_programs(enabled)
            """)

            # Research Snapshots (P2.1)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    program_id TEXT NOT NULL,
                    window_since TEXT NULL,
                    window_until TEXT NULL,
                    captured_at TEXT NOT NULL,
                    paper_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(program_id) REFERENCES research_programs(program_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_research_snapshots_program_captured
                ON research_snapshots(program_id, captured_at DESC)
            """)

            # Research Snapshot Items (P2.1)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_snapshot_items (
                    snapshot_id TEXT NOT NULL,
                    paper_id TEXT NOT NULL,
                    source_order INTEGER NOT NULL,
                    PRIMARY KEY(snapshot_id, paper_id),
                    FOREIGN KEY(snapshot_id) REFERENCES research_snapshots(snapshot_id),
                    FOREIGN KEY(paper_id) REFERENCES papers(paper_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_research_snapshot_items_paper
                ON research_snapshot_items(paper_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_research_snapshot_items_snapshot_order
                ON research_snapshot_items(snapshot_id, source_order)
            """)

    # ========== 模块 1: Paper Source Registry ==========

    def get_source(self, source_id: str) -> PaperSource | None:
        """获取单个 paper source"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM paper_sources WHERE source_id = ?", (source_id,)
            ).fetchone()
            return self._row_to_source(row) if row else None

    def list_sources(
        self,
        platform: str | None = None,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaperSource]:
        """列出 paper sources"""
        with self.db.connect() as conn:
            query = "SELECT * FROM paper_sources WHERE 1=1"
            params: list[Any] = []

            if platform:
                query += " AND platform = ?"
                params.append(platform)
            if enabled is not None:
                query += " AND enabled = ?"
                params.append(1 if enabled else 0)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_source(row) for row in rows]

    def upsert_source(
        self,
        source_id: str | None,
        platform: str,
        endpoint: str,
        name: str,
        config_json: str = "{}",
        cursor_json: str | None = None,
        enabled: bool = True,
        schedule_minutes: int | None = None,
    ) -> PaperSource:
        """创建或更新 paper source"""
        now = datetime.utcnow().isoformat()

        if not source_id:
            source_id = self._generate_source_id(platform, endpoint)

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_sources (
                    source_id, platform, endpoint, name, config_json, cursor_json,
                    enabled, schedule_minutes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    name = excluded.name,
                    config_json = excluded.config_json,
                    cursor_json = excluded.cursor_json,
                    enabled = excluded.enabled,
                    schedule_minutes = excluded.schedule_minutes,
                    updated_at = excluded.updated_at
                """,
                (
                    source_id,
                    platform,
                    endpoint,
                    name,
                    config_json,
                    cursor_json,
                    1 if enabled else 0,
                    schedule_minutes,
                    now,
                    now,
                ),
            )

        return self.get_source(source_id)  # type: ignore

    def update_source(
        self, source_id: str, **updates: Any
    ) -> PaperSource | None:
        """更新 paper source 字段"""
        allowed_fields = {
            "name",
            "config_json",
            "cursor_json",
            "enabled",
            "schedule_minutes",
            "last_run_at",
            "error_count",
            "last_error",
        }
        updates = {k: v for k, v in updates.items() if k in allowed_fields}
        if not updates:
            return self.get_source(source_id)

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [source_id]

        with self.db.connect() as conn:
            conn.execute(
                f"UPDATE paper_sources SET {set_clause} WHERE source_id = ?",
                values,
            )

        return self.get_source(source_id)

    def record_source_error(self, source_id: str, error_message: str) -> None:
        """Atomically bump error_count and record last_error for a paper source."""
        now = datetime.utcnow().isoformat()
        err = (error_message or "")[:500]
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE paper_sources SET
                    error_count = error_count + 1,
                    last_error = ?,
                    updated_at = ?
                WHERE source_id = ?
                """,
                (err, now, source_id),
            )

    def delete_source(self, source_id: str) -> bool:
        """删除 paper source（不级联删除 papers）"""
        with self.db.connect() as conn:
            # 删除 source_items 和 runs
            conn.execute(
                "DELETE FROM paper_source_items WHERE source_id = ?", (source_id,)
            )
            conn.execute("DELETE FROM paper_runs WHERE source_id = ?", (source_id,))
            cursor = conn.execute(
                "DELETE FROM paper_sources WHERE source_id = ?", (source_id,)
            )
            return cursor.rowcount > 0

    # ========== 模块 2: Paper Canonical Store ==========

    def upsert_paper(self, record: PaperRecord) -> str:
        """插入或更新 paper（以 canonical_id 为幂等键）"""
        now = datetime.utcnow().isoformat()
        paper_id = self._generate_paper_id(record.canonical_id)

        authors_json = json.dumps(record.authors) if record.authors else None
        external_ids_json = (
            json.dumps(record.external_ids) if record.external_ids else None
        )
        raw_meta_json = json.dumps(record.raw_meta) if record.raw_meta else None

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO papers (
                    paper_id, canonical_id, canonical_url, title, abstract,
                    published_at, authors_json, venue, doi, pdf_url,
                    external_ids_json, raw_meta_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_id) DO UPDATE SET
                    canonical_url = excluded.canonical_url,
                    title = excluded.title,
                    abstract = excluded.abstract,
                    published_at = excluded.published_at,
                    authors_json = excluded.authors_json,
                    venue = excluded.venue,
                    doi = excluded.doi,
                    pdf_url = excluded.pdf_url,
                    external_ids_json = excluded.external_ids_json,
                    raw_meta_json = excluded.raw_meta_json,
                    updated_at = excluded.updated_at
                """,
                (
                    paper_id,
                    record.canonical_id,
                    record.canonical_url,
                    record.title,
                    record.abstract,
                    record.published_at.isoformat() if record.published_at else None,
                    authors_json,
                    record.venue,
                    record.doi,
                    record.pdf_url,
                    external_ids_json,
                    raw_meta_json,
                    now,
                    now,
                ),
            )

            # 返回实际的 paper_id（可能是已存在的）
            row = conn.execute(
                "SELECT paper_id FROM papers WHERE canonical_id = ?",
                (record.canonical_id,),
            ).fetchone()
            return row[0]

    def get_paper(self, paper_id: str) -> Paper | None:
        """获取单个 paper"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE paper_id = ?", (paper_id,)
            ).fetchone()
            return self._row_to_paper(row) if row else None

    def list_papers(
        self, limit: int = 50, offset: int = 0
    ) -> list[Paper]:
        """列出 papers（按 published_at 倒序）"""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM papers
                ORDER BY (published_at IS NULL) ASC, published_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            return [self._row_to_paper(row) for row in rows]

    # ========== 模块 3: Paper Source Item Index ==========

    def mark_seen(
        self, source_id: str, item_key: str, paper_id: str, seen_at: datetime
    ) -> None:
        """标记 source 已见过某 paper item（upsert）"""
        seen_at_str = seen_at.isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_source_items (
                    source_id, item_key, paper_id, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id, item_key) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at
                """,
                (source_id, item_key, paper_id, seen_at_str, seen_at_str),
            )

    def has_seen(self, source_id: str, item_key: str) -> bool:
        """检查 source 是否已见过某 item"""
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM paper_source_items
                WHERE source_id = ? AND item_key = ?
                """,
                (source_id, item_key),
            ).fetchone()
            return row is not None

    def list_papers_by_source(
        self, source_id: str, limit: int = 50, offset: int = 0
    ) -> list[Paper]:
        """列出某 source 采集过的 papers（按 last_seen_at 倒序）"""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT p.* FROM papers p
                JOIN paper_source_items psi ON p.paper_id = psi.paper_id
                WHERE psi.source_id = ?
                ORDER BY psi.last_seen_at DESC
                LIMIT ? OFFSET ?
                """,
                (source_id, limit, offset),
            ).fetchall()
            return [self._row_to_paper(row) for row in rows]

    def list_papers_by_sources_and_window(
        self,
        source_ids: list[str],
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """列出多个 sources 在时间窗口内的 papers

        Args:
            source_ids: List of source IDs to query
            since: Start datetime (inclusive), None for no lower bound
            until: End datetime (exclusive), None for no upper bound
            limit: Maximum number of papers to return
            offset: Number of papers to skip

        Returns:
            List of Paper objects ordered by published_at DESC
        """
        # Edge case: empty source_ids
        if not source_ids:
            return []

        with self.db.connect() as conn:
            # Build dynamic WHERE clause
            query = """
                SELECT DISTINCT p.* FROM papers p
                JOIN paper_source_items psi ON p.paper_id = psi.paper_id
                WHERE psi.source_id IN ({})
            """.format(",".join("?" * len(source_ids)))

            params: list[Any] = list(source_ids)

            # Add datetime filters if provided
            if since is not None:
                query += " AND p.published_at >= ?"
                params.append(since.isoformat())

            if until is not None:
                query += " AND p.published_at < ?"
                params.append(until.isoformat())

            # Order and pagination
            query += " ORDER BY (p.published_at IS NULL) ASC, p.published_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_paper(row) for row in rows]

    # ========== 模块 4: Paper Runs ==========

    def create_run(
        self, source_id: str, job_id: str | None = None
    ) -> str:
        """创建 paper run 记录"""
        # run_id 追溯主键优先对齐 job_id（P0-5）：避免“同 source 同秒两次 run”碰撞
        run_id = job_id or f"run_{uuid.uuid4().hex[:16]}"
        started_at = datetime.utcnow().isoformat()

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_runs (
                    run_id, source_id, job_id, status, started_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, source_id, job_id, "running", started_at),
            )

        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str,
        fetched_count: int = 0,
        processed_count: int = 0,
        cursor_before: dict | None = None,
        cursor_after: dict | None = None,
        metrics: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        """完成 paper run"""
        finished_at = datetime.utcnow().isoformat()

        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE paper_runs SET
                    status = ?,
                    finished_at = ?,
                    fetched_count = ?,
                    processed_count = ?,
                    cursor_before_json = ?,
                    cursor_after_json = ?,
                    metrics_json = ?,
                    error_message = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    finished_at,
                    fetched_count,
                    processed_count,
                    json.dumps(cursor_before) if cursor_before else None,
                    json.dumps(cursor_after) if cursor_after else None,
                    json.dumps(metrics) if metrics else None,
                    error_message,
                    run_id,
                ),
            )

    def list_runs(
        self, source_id: str, limit: int = 20, offset: int = 0
    ) -> list[PaperRun]:
        """列出某 source 的 run 历史"""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM paper_runs
                WHERE source_id = ?
                ORDER BY started_at DESC
                LIMIT ? OFFSET ?
                """,
                (source_id, limit, offset),
            ).fetchall()
            return [self._row_to_run(row) for row in rows]

    # ========== Helper Methods ==========

    def _generate_source_id(self, platform: str, endpoint: str) -> str:
        """生成确定性 source_id"""
        key = f"{platform}:{endpoint}".encode("utf-8")
        hash_hex = hashlib.sha256(key).hexdigest()[:12]
        return f"paper_{platform}_{hash_hex}"

    def _generate_paper_id(self, canonical_id: str) -> str:
        """生成确定性 paper_id"""
        hash_hex = hashlib.sha256(canonical_id.encode("utf-8")).hexdigest()[:16]
        return f"paper_{hash_hex}"

    def _row_to_source(self, row: Any) -> PaperSource:
        """Convert DB row to PaperSource"""
        return PaperSource(
            source_id=row[0],
            platform=row[1],
            endpoint=row[2],
            name=row[3],
            config_json=row[4],
            cursor_json=row[5],
            enabled=bool(row[6]),
            schedule_minutes=row[7],
            last_run_at=datetime.fromisoformat(row[8]) if row[8] else None,
            error_count=row[9],
            last_error=row[10],
            created_at=datetime.fromisoformat(row[11]) if row[11] else None,
            updated_at=datetime.fromisoformat(row[12]) if row[12] else None,
        )

    def _row_to_paper(self, row: Any) -> Paper:
        """Convert DB row to Paper"""
        return Paper(
            paper_id=row[0],
            canonical_id=row[1],
            canonical_url=row[2],
            title=row[3],
            abstract=row[4],
            published_at=datetime.fromisoformat(row[5]) if row[5] else None,
            authors_json=row[6],
            venue=row[7],
            doi=row[8],
            pdf_url=row[9],
            external_ids_json=row[10],
            raw_meta_json=row[11],
            created_at=datetime.fromisoformat(row[12]) if row[12] else None,
            updated_at=datetime.fromisoformat(row[13]) if row[13] else None,
        )

    def _row_to_run(self, row: Any) -> PaperRun:
        """Convert DB row to PaperRun"""
        return PaperRun(
            run_id=row[0],
            source_id=row[1],
            job_id=row[2],
            status=row[3],
            started_at=datetime.fromisoformat(row[4]),
            finished_at=datetime.fromisoformat(row[5]) if row[5] else None,
            fetched_count=row[6],
            processed_count=row[7],
            error_message=row[8],
            metrics_json=row[9],
            cursor_before_json=row[10],
            cursor_after_json=row[11],
        )

    # ========== P2.1: Research Program CRUD ==========

    def upsert_research_program(
        self,
        name: str,
        description: str | None,
        source_ids: list[str],
        filters: dict | None = None,
        enabled: bool = True,
    ) -> ResearchProgram:
        """Create or update research program

        Args:
            name: Program name (unique)
            description: Optional description
            source_ids: List of paper_source IDs to include
            filters: Optional filters {"categories": [...], "keywords": [...]}
            enabled: Whether program is active

        Returns:
            ResearchProgram object
        """
        program_id = self._generate_program_id(name)
        now = datetime.utcnow().isoformat()

        source_ids_json = json.dumps(source_ids)
        filters_json = json.dumps(filters or {})

        with self.db.connect() as conn:
            conn.execute("""
                INSERT INTO research_programs (
                    program_id, name, description, source_ids, filters_json,
                    enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(program_id) DO UPDATE SET
                    description = excluded.description,
                    source_ids = excluded.source_ids,
                    filters_json = excluded.filters_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
            """, (program_id, name, description, source_ids_json, filters_json,
                  int(enabled), now, now))
            conn.commit()

        return self.get_research_program(program_id)  # type: ignore

    def get_research_program(self, program_id: str) -> ResearchProgram | None:
        """Get research program by ID"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_programs WHERE program_id = ?",
                (program_id,)
            ).fetchone()
        return self._row_to_research_program(row) if row else None

    def update_research_program(
        self,
        program_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        source_ids: list[str] | None = None,
        filters: dict | None = None,
        enabled: bool | None = None,
    ) -> ResearchProgram | None:
        """Update a research program by stable program_id.

        Note: This differs from upsert_research_program(), whose program_id is name-derived.
        """
        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if source_ids is not None:
            updates["source_ids"] = json.dumps(source_ids)
        if filters is not None:
            updates["filters_json"] = json.dumps(filters)
        if enabled is not None:
            updates["enabled"] = int(enabled)

        if not updates:
            return self.get_research_program(program_id)

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        params = list(updates.values()) + [program_id]

        with self.db.connect() as conn:
            cur = conn.execute(
                f"UPDATE research_programs SET {set_clause} WHERE program_id = ?",
                params,
            )
            conn.commit()

        if cur.rowcount <= 0:
            return None
        return self.get_research_program(program_id)

    def list_research_programs(
        self,
        enabled: bool | None = None,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ResearchProgram]:
        """List research programs"""
        query = "SELECT * FROM research_programs WHERE 1=1"
        params: list[Any] = []

        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)
        elif enabled_only:
            query += " AND enabled = 1"

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_research_program(row) for row in rows]

    def delete_research_program(self, program_id: str) -> bool:
        """Delete research program"""
        with self.db.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM research_programs WHERE program_id = ?",
                (program_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    # ========== P2.1: Research Snapshot CRUD ==========

    def create_research_snapshot(
        self,
        program_id: str,
        window_since: str | None,
        window_until: str | None,
        captured_at: datetime,
    ) -> str:
        """Create research snapshot

        Args:
            program_id: Research program ID
            window_since: Start of time window (ISO datetime)
            window_until: End of time window (ISO datetime)
            captured_at: When snapshot was captured

        Returns:
            snapshot_id
        """
        snapshot_id = self._generate_research_snapshot_id(program_id, captured_at)
        now = datetime.utcnow().isoformat()

        with self.db.connect() as conn:
            conn.execute("""
                INSERT INTO research_snapshots (
                    snapshot_id, program_id, window_since, window_until,
                    captured_at, paper_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?)
            """, (snapshot_id, program_id, window_since, window_until,
                  captured_at.isoformat(), now))
            conn.commit()

        return snapshot_id

    def get_research_snapshot(self, snapshot_id: str) -> ResearchSnapshot | None:
        """Get research snapshot by ID"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_snapshots WHERE snapshot_id = ?",
                (snapshot_id,)
            ).fetchone()
        return self._row_to_research_snapshot(row) if row else None

    def list_research_snapshots(
        self,
        program_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ResearchSnapshot]:
        """List snapshots for a research program"""
        with self.db.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM research_snapshots
                WHERE program_id = ?
                ORDER BY captured_at DESC
                LIMIT ? OFFSET ?
            """, (program_id, limit, offset)).fetchall()

        return [self._row_to_research_snapshot(row) for row in rows]

    def get_latest_research_snapshot(
        self,
        program_id: str
    ) -> ResearchSnapshot | None:
        """Get most recent snapshot for a program"""
        with self.db.connect() as conn:
            row = conn.execute("""
                SELECT * FROM research_snapshots
                WHERE program_id = ?
                ORDER BY captured_at DESC
                LIMIT 1
            """, (program_id,)).fetchone()

        return self._row_to_research_snapshot(row) if row else None

    def add_research_snapshot_items(
        self,
        snapshot_id: str,
        paper_ids: list[str],
    ) -> None:
        """Add papers to research snapshot

        Args:
            snapshot_id: Snapshot ID
            paper_ids: List of paper IDs (ordered)
        """
        with self.db.connect() as conn:
            # Insert items with source_order
            for order, paper_id in enumerate(paper_ids, start=1):
                conn.execute("""
                    INSERT INTO research_snapshot_items (
                        snapshot_id, paper_id, source_order
                    )
                    VALUES (?, ?, ?)
                """, (snapshot_id, paper_id, order))

            # Update paper_count
            conn.execute("""
                UPDATE research_snapshots
                SET paper_count = ?
                WHERE snapshot_id = ?
            """, (len(paper_ids), snapshot_id))

            conn.commit()

    def list_research_snapshot_items(
        self,
        snapshot_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[tuple[str, int]]:
        """List papers in snapshot with their order

        Returns:
            List of (paper_id, source_order) tuples
        """
        with self.db.connect() as conn:
            rows = conn.execute("""
                SELECT paper_id, source_order
                FROM research_snapshot_items
                WHERE snapshot_id = ?
                ORDER BY source_order
                LIMIT ? OFFSET ?
            """, (snapshot_id, limit, offset)).fetchall()

        return [(row[0], row[1]) for row in rows]

    # ========== P2.1: Helper Methods ==========

    def _generate_program_id(self, name: str) -> str:
        """Generate deterministic program ID from name"""
        key = f"research_program:{name}".encode()
        hash_hex = hashlib.sha256(key).hexdigest()[:16]
        return f"rp_{hash_hex}"

    def _generate_research_snapshot_id(
        self,
        program_id: str,
        captured_at: datetime
    ) -> str:
        """Generate deterministic snapshot ID"""
        key = f"{program_id}:{captured_at.isoformat()}".encode()
        hash_hex = hashlib.sha256(key).hexdigest()[:16]
        return f"rsnap_{hash_hex}"

    def _row_to_research_program(self, row: Any) -> ResearchProgram:
        """Convert DB row to ResearchProgram"""
        return ResearchProgram(
            program_id=row[0],
            name=row[1],
            description=row[2],
            source_ids=row[3],
            filters_json=row[4],
            enabled=bool(row[5]),
            last_run_at=datetime.fromisoformat(row[6]) if row[6] else None,
            created_at=datetime.fromisoformat(row[7]) if row[7] else None,
            updated_at=datetime.fromisoformat(row[8]) if row[8] else None,
        )

    def _row_to_research_snapshot(self, row: Any) -> ResearchSnapshot:
        """Convert DB row to ResearchSnapshot"""
        return ResearchSnapshot(
            snapshot_id=row[0],
            program_id=row[1],
            window_since=row[2],
            window_until=row[3],
            captured_at=datetime.fromisoformat(row[4]),
            paper_count=row[5],
            created_at=datetime.fromisoformat(row[6]) if row[6] else None,
        )
