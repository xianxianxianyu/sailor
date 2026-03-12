"""BoardRepository - Board 数据访问层

提供 Board、BoardSnapshot 和 BoardSnapshotItem 的 CRUD 操作
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from core.board.models import Board, BoardSnapshot, BoardSnapshotItem
from core.storage.db import Database


class BoardRepository:
    """Board 数据访问层"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """创建 BoardEngine 所需的表"""
        with self.db.connect() as conn:
            # boards 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS boards (
                    board_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(provider, kind, name)
                )
            """)

            # board_snapshots 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS board_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    board_id TEXT NOT NULL,
                    window_since TEXT NULL,
                    window_until TEXT NULL,
                    captured_at TEXT NOT NULL,
                    raw_capture_ref TEXT NULL,
                    adapter_version TEXT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(board_id) REFERENCES boards(board_id)
                )
            """)

            # board_snapshot_items 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS board_snapshot_items (
                    snapshot_id TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    source_order INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    meta_json TEXT NULL,
                    PRIMARY KEY(snapshot_id, item_key),
                    FOREIGN KEY(snapshot_id) REFERENCES board_snapshots(snapshot_id)
                )
            """)

            # 索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_boards_provider_enabled
                ON boards(provider, enabled)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_board_snapshots_board_captured
                ON board_snapshots(board_id, captured_at DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_board_snapshot_items_snapshot
                ON board_snapshot_items(snapshot_id, source_order)
            """)

            conn.commit()

    # ========== ID 生成方法 ==========

    def _generate_board_id(self, provider: str, kind: str, name: str) -> str:
        """生成确定性 board_id"""
        key = f"{provider}:{kind}:{name}".encode("utf-8")
        hash_hex = hashlib.sha256(key).hexdigest()[:12]
        return f"board_{provider}_{hash_hex}"

    def _generate_snapshot_id(self, board_id: str, captured_at: datetime) -> str:
        """生成确定性 snapshot_id"""
        key = f"{board_id}:{captured_at.isoformat()}".encode("utf-8")
        hash_hex = hashlib.sha256(key).hexdigest()[:16]
        return f"snap_{hash_hex}"

    # ========== Board CRUD 方法 ==========

    def upsert_board(
        self,
        provider: str,
        kind: str,
        name: str,
        config_json: str,
        enabled: bool = True,
    ) -> Board:
        """创建或更新 Board"""
        board_id = self._generate_board_id(provider, kind, name)
        now = datetime.utcnow().isoformat()

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO boards (
                    board_id, provider, kind, name, config_json, enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(board_id) DO UPDATE SET
                    name = excluded.name,
                    config_json = excluded.config_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (board_id, provider, kind, name, config_json, int(enabled), now, now),
            )
            conn.commit()

        return self.get_board(board_id)  # type: ignore

    def get_board(self, board_id: str) -> Board | None:
        """获取单个 Board"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM boards WHERE board_id = ?",
                (board_id,),
            ).fetchone()

        return self._row_to_board(row) if row else None

    def list_boards(
        self,
        provider: str | None = None,
        enabled: bool | None = None,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Board]:
        """列出 Boards"""
        query = "SELECT * FROM boards WHERE 1=1"
        params: list[Any] = []

        if provider:
            query += " AND provider = ?"
            params.append(provider)

        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)
        elif enabled_only:
            query += " AND enabled = 1"

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_board(row) for row in rows]

    def update_board(self, board_id: str, **updates: Any) -> Board | None:
        """更新 Board"""
        allowed_fields = {"name", "config_json", "enabled", "last_run_at"}
        updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not updates:
            return self.get_board(board_id)

        updates["updated_at"] = datetime.utcnow().isoformat()

        # 处理 enabled 字段（转换为 INTEGER）
        if "enabled" in updates:
            updates["enabled"] = int(updates["enabled"])

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [board_id]

        with self.db.connect() as conn:
            conn.execute(
                f"UPDATE boards SET {set_clause} WHERE board_id = ?",
                values,
            )
            conn.commit()

        return self.get_board(board_id)

    def delete_board(self, board_id: str) -> bool:
        """删除 Board"""
        with self.db.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM boards WHERE board_id = ?",
                (board_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ========== Snapshot CRUD 方法 ==========

    def create_snapshot(
        self,
        board_id: str,
        window_since: str | None,
        window_until: str | None,
        captured_at: datetime,
        raw_capture_ref: str | None = None,
        adapter_version: str | None = None,
    ) -> str:
        """创建 BoardSnapshot"""
        snapshot_id = self._generate_snapshot_id(board_id, captured_at)
        now = datetime.utcnow().isoformat()

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO board_snapshots (
                    snapshot_id, board_id, window_since, window_until,
                    captured_at, raw_capture_ref, adapter_version, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    board_id,
                    window_since,
                    window_until,
                    captured_at.isoformat(),
                    raw_capture_ref,
                    adapter_version,
                    now,
                ),
            )
            conn.commit()

        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> BoardSnapshot | None:
        """获取单个 BoardSnapshot"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM board_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()

        return self._row_to_snapshot(row) if row else None

    def list_snapshots(
        self,
        board_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BoardSnapshot]:
        """列出 Board 的所有快照"""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM board_snapshots
                WHERE board_id = ?
                ORDER BY captured_at DESC
                LIMIT ? OFFSET ?
                """,
                (board_id, limit, offset),
            ).fetchall()

        return [self._row_to_snapshot(row) for row in rows]

    def get_latest_snapshot(self, board_id: str) -> BoardSnapshot | None:
        """获取最新快照"""
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM board_snapshots
                WHERE board_id = ?
                ORDER BY captured_at DESC
                LIMIT 1
                """,
                (board_id,),
            ).fetchone()

        return self._row_to_snapshot(row) if row else None

    # ========== Snapshot Items 方法 ==========

    def add_snapshot_items(
        self,
        snapshot_id: str,
        items: list[dict[str, Any]],
    ) -> None:
        """添加快照条目"""
        with self.db.connect() as conn:
            for item in items:
                conn.execute(
                    """
                    INSERT INTO board_snapshot_items (
                        snapshot_id, item_key, source_order, title, url, meta_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(snapshot_id, item_key) DO UPDATE SET
                        source_order = excluded.source_order,
                        title = excluded.title,
                        url = excluded.url,
                        meta_json = excluded.meta_json
                    """,
                    (
                        snapshot_id,
                        item["item_key"],
                        item["source_order"],
                        item["title"],
                        item["url"],
                        item.get("meta_json"),
                    ),
                )
            conn.commit()

    def list_snapshot_items(
        self,
        snapshot_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[BoardSnapshotItem]:
        """列出快照的所有条目"""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM board_snapshot_items
                WHERE snapshot_id = ?
                ORDER BY source_order ASC
                LIMIT ? OFFSET ?
                """,
                (snapshot_id, limit, offset),
            ).fetchall()

        return [self._row_to_snapshot_item(row) for row in rows]

    # ========== 辅助方法 ==========

    def _row_to_board(self, row: Any) -> Board:
        """将数据库行转换为 Board 对象"""
        return Board(
            board_id=row[0],
            provider=row[1],
            kind=row[2],
            name=row[3],
            config_json=row[4],
            enabled=bool(row[5]),
            last_run_at=datetime.fromisoformat(row[6]) if row[6] else None,
            created_at=datetime.fromisoformat(row[7]) if row[7] else None,
            updated_at=datetime.fromisoformat(row[8]) if row[8] else None,
        )

    def _row_to_snapshot(self, row: Any) -> BoardSnapshot:
        """将数据库行转换为 BoardSnapshot 对象"""
        return BoardSnapshot(
            snapshot_id=row[0],
            board_id=row[1],
            window_since=row[2],
            window_until=row[3],
            captured_at=datetime.fromisoformat(row[4]),
            raw_capture_ref=row[5],
            adapter_version=row[6],
            created_at=datetime.fromisoformat(row[7]) if row[7] else None,
        )

    def _row_to_snapshot_item(self, row: Any) -> BoardSnapshotItem:
        """将数据库行转换为 BoardSnapshotItem 对象"""
        return BoardSnapshotItem(
            snapshot_id=row[0],
            item_key=row[1],
            source_order=row[2],
            title=row[3],
            url=row[4],
            meta_json=row[5],
        )
