from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from core.models import KnowledgeBase, KnowledgeBaseItem, Resource
from core.storage.db import Database


class ResourceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, resource: Resource) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO resources (
                    resource_id,
                    canonical_url,
                    source,
                    provenance_json,
                    title,
                    published_at,
                    text,
                    original_url,
                    topics_json,
                    summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_url)
                DO UPDATE SET
                    source=excluded.source,
                    provenance_json=excluded.provenance_json,
                    title=excluded.title,
                    published_at=excluded.published_at,
                    text=excluded.text,
                    original_url=excluded.original_url,
                    topics_json=excluded.topics_json,
                    summary=excluded.summary
                """,
                (
                    resource.resource_id,
                    resource.canonical_url,
                    resource.source,
                    json.dumps(resource.provenance),
                    resource.title,
                    resource.published_at.isoformat() if resource.published_at else None,
                    resource.text,
                    resource.original_url,
                    json.dumps(resource.topics),
                    resource.summary,
                ),
            )

    def list_resources(self, topic: str | None = None, status: str = "all") -> list[Resource]:
        where_clauses = []
        params: list[str] = []

        if topic:
            where_clauses.append("topics_json LIKE ?")
            params.append(f'%"{topic}"%')

        if status == "inbox":
            where_clauses.append(
                "NOT EXISTS (SELECT 1 FROM kb_items k WHERE k.resource_id = resources.resource_id)"
            )

        where_sql = ""
        if where_clauses:
            where_sql = f"WHERE {' AND '.join(where_clauses)}"

        query = f"""
            SELECT *
            FROM resources
            {where_sql}
            ORDER BY COALESCE(published_at, created_at) DESC
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_resource(row) for row in rows]

    def get_resource(self, resource_id: str) -> Resource | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM resources WHERE resource_id = ?",
                (resource_id,),
            ).fetchone()
        return self._row_to_resource(row) if row else None

    def list_resource_kbs(self, resource_id: str) -> list[KnowledgeBase]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT kb.kb_id, kb.name, kb.description
                FROM knowledge_bases kb
                JOIN kb_items item ON kb.kb_id = item.kb_id
                WHERE item.resource_id = ?
                ORDER BY kb.name ASC
                """,
                (resource_id,),
            ).fetchall()
        return [KnowledgeBase(kb_id=row["kb_id"], name=row["name"], description=row["description"]) for row in rows]

    @staticmethod
    def _row_to_resource(row: sqlite3.Row) -> Resource:
        published_at = datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
        return Resource(
            resource_id=row["resource_id"],
            canonical_url=row["canonical_url"],
            source=row["source"],
            provenance=json.loads(row["provenance_json"]),
            title=row["title"],
            published_at=published_at,
            text=row["text"],
            original_url=row["original_url"],
            topics=json.loads(row["topics_json"]),
            summary=row["summary"],
        )


class KnowledgeBaseRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def ensure_defaults(self) -> None:
        defaults = [
            KnowledgeBase(kb_id="kb_llm", name="LLM Notes", description="LLM and AI engineering"),
            KnowledgeBase(kb_id="kb_platform", name="Platform", description="Infra and platform engineering"),
            KnowledgeBase(kb_id="kb_product", name="Product Engineering", description="Frontend and product design"),
        ]
        with self.db.connect() as conn:
            for kb in defaults:
                conn.execute(
                    """
                    INSERT INTO knowledge_bases (kb_id, name, description)
                    VALUES (?, ?, ?)
                    ON CONFLICT(kb_id) DO NOTHING
                    """,
                    (kb.kb_id, kb.name, kb.description),
                )

    def list_all(self) -> list[KnowledgeBase]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT kb_id, name, description FROM knowledge_bases ORDER BY name ASC"
            ).fetchall()
        return [KnowledgeBase(kb_id=row["kb_id"], name=row["name"], description=row["description"]) for row in rows]

    def add_item(self, kb_id: str, resource_id: str) -> KnowledgeBaseItem:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO kb_items (kb_id, resource_id)
                VALUES (?, ?)
                ON CONFLICT(kb_id, resource_id) DO NOTHING
                """,
                (kb_id, resource_id),
            )
            row = conn.execute(
                """
                SELECT kb_id, resource_id, added_at
                FROM kb_items
                WHERE kb_id = ? AND resource_id = ?
                """,
                (kb_id, resource_id),
            ).fetchone()

        return KnowledgeBaseItem(
            kb_id=row["kb_id"],
            resource_id=row["resource_id"],
            added_at=datetime.fromisoformat(row["added_at"]),
        )
