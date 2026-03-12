from __future__ import annotations

from datetime import datetime, timezone

from core.storage.db import Database


class KBGraphRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Nodes (dynamically derived from kb_items JOIN resources)
    # ------------------------------------------------------------------

    def list_nodes(self, kb_id: str, limit: int | None = None) -> list[dict]:
        """Return all resource nodes for the KB, optionally limited."""
        with self.db.connect() as conn:
            query = """
                SELECT r.resource_id as id, r.title, r.summary,
                       r.original_url as url, r.topics_json, ki.added_at
                FROM kb_items ki
                JOIN resources r ON r.resource_id = ki.resource_id
                WHERE ki.kb_id = ?
                ORDER BY ki.added_at DESC
                """
            if limit:
                query += f" LIMIT {limit}"
            rows = conn.execute(query, (kb_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_node(self, kb_id: str, node_id: str) -> dict | None:
        """Get a single node by resource_id."""
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT r.resource_id as id, r.title, r.summary,
                       r.original_url as url, r.topics_json, ki.added_at
                FROM kb_items ki
                JOIN resources r ON r.resource_id = ki.resource_id
                WHERE ki.kb_id = ? AND r.resource_id = ?
                """,
                (kb_id, node_id),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    def list_edges(self, kb_id: str, status: str = "active") -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM kb_graph_edges WHERE kb_id=? AND status=?",
                (kb_id, status),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_neighbors(self, kb_id: str, node_id: str) -> list[dict]:
        """Return all active edges incident to node_id."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM kb_graph_edges
                WHERE kb_id=? AND status='active'
                  AND (node_a_id=? OR node_b_id=?)
                """,
                (kb_id, node_id, node_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_edge(
        self,
        kb_id: str,
        node_a: str,
        node_b: str,
        reason: str,
        reason_type: str | None = None,
        created_by: str = "user",
        created_run_id: str | None = None,
    ) -> dict:
        """Create or update an edge; canonically sorted so a <= b."""
        a, b = sorted([node_a, node_b])
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO kb_graph_edges
                    (kb_id, node_a_id, node_b_id, status, reason, reason_type,
                     created_by, created_run_id, created_at, updated_at)
                VALUES (?,?,?,'active',?,?,?,?,?,?)
                ON CONFLICT(kb_id, node_a_id, node_b_id)
                DO UPDATE SET
                    reason=CASE WHEN frozen=0 THEN excluded.reason ELSE reason END,
                    reason_type=CASE WHEN frozen=0 THEN excluded.reason_type ELSE reason_type END,
                    status='active',
                    created_run_id=excluded.created_run_id,
                    updated_at=excluded.updated_at
                """,
                (kb_id, a, b, reason, reason_type, created_by, created_run_id, now, now),
            )
            row = conn.execute(
                "SELECT * FROM kb_graph_edges WHERE kb_id=? AND node_a_id=? AND node_b_id=?",
                (kb_id, a, b),
            ).fetchone()
        return dict(row)

    def soft_delete_edge(
        self, kb_id: str, node_a: str, node_b: str, deleted_by: str = "user", deleted_run_id: str | None = None
    ) -> bool:
        a, b = sorted([node_a, node_b])
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE kb_graph_edges
                SET status='deleted', deleted_at=?, deleted_by=?, deleted_run_id=?, updated_at=?
                WHERE kb_id=? AND node_a_id=? AND node_b_id=? AND status='active'
                """,
                (now, deleted_by, deleted_run_id, now, kb_id, a, b),
            )
        return cursor.rowcount > 0

    def freeze_edge(self, kb_id: str, node_a: str, node_b: str) -> bool:
        a, b = sorted([node_a, node_b])
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE kb_graph_edges SET frozen=1, updated_at=CURRENT_TIMESTAMP "
                "WHERE kb_id=? AND node_a_id=? AND node_b_id=?",
                (kb_id, a, b),
            )
        return cursor.rowcount > 0

    def unfreeze_edge(self, kb_id: str, node_a: str, node_b: str) -> bool:
        a, b = sorted([node_a, node_b])
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE kb_graph_edges SET frozen=0, updated_at=CURRENT_TIMESTAMP "
                "WHERE kb_id=? AND node_a_id=? AND node_b_id=?",
                (kb_id, a, b),
            )
        return cursor.rowcount > 0

    def get_subgraph(
        self, kb_id: str, start_node_id: str, depth: int = 2
    ) -> tuple[list[dict], list[dict]]:
        """Return subgraph using BFS from start_node_id up to depth hops."""
        visited = set()
        nodes = []
        edges = []
        queue = [(start_node_id, 0)]

        while queue:
            node_id, current_depth = queue.pop(0)
            if node_id in visited or current_depth > depth:
                continue
            visited.add(node_id)

            node = self.get_node(kb_id, node_id)
            if node:
                nodes.append(node)

            if current_depth < depth:
                neighbors = self.get_neighbors(kb_id, node_id)
                for edge in neighbors:
                    if edge["status"] == "active":
                        edge_id = (edge["node_a_id"], edge["node_b_id"])
                        if edge_id not in {(e["node_a_id"], e["node_b_id"]) for e in edges}:
                            edges.append(edge)
                        other_id = (
                            edge["node_b_id"]
                            if edge["node_a_id"] == node_id
                            else edge["node_a_id"]
                        )
                        if other_id not in visited:
                            queue.append((other_id, current_depth + 1))

        return nodes, edges

    # ------------------------------------------------------------------
    # Auto-linking support (P1)
    # ------------------------------------------------------------------

    def list_recent_nodes(self, kb_id: str, limit: int = 20) -> list[dict]:
        """Return most recently added nodes for candidate recall."""
        return self.list_nodes(kb_id, limit=limit)

    def get_deleted_pairs(self, kb_id: str) -> set[tuple[str, str]]:
        """Return set of (node_a, node_b) pairs that have been deleted by user."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT node_a_id, node_b_id FROM kb_graph_edges
                WHERE kb_id=? AND status='deleted' AND deleted_by='user'
                """,
                (kb_id,),
            ).fetchall()
        return {(row["node_a_id"], row["node_b_id"]) for row in rows}

    def list_edges_by_run(self, kb_id: str, run_id: str) -> list[dict]:
        """Return all edges created by a specific run."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM kb_graph_edges WHERE kb_id=? AND created_run_id=?",
                (kb_id, run_id),
            ).fetchall()
        return [dict(row) for row in rows]
