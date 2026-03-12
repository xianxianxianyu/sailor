from __future__ import annotations

import logging
from typing import Any

from core.models import Job
from core.runner.handlers import JobHandler, RunContext
from core.storage.kg_graph_repository import KBGraphRepository
from .link_engine import KGLinkEngine

logger = logging.getLogger(__name__)


class KGAddNodeHandler(JobHandler):
    """
    Handler for kg_add_node jobs.

    When a resource is added to a KB, this handler:
    1. Recalls recent candidate nodes (time-sorted, top 20)
    2. Queries blocked pairs (user-deleted edges)
    3. Uses LLM to infer semantic connections
    4. Creates edges with created_run_id tracking
    """

    def __init__(
        self,
        kg_repo: KBGraphRepository,
        link_engine: KGLinkEngine,
    ) -> None:
        self.kg_repo = kg_repo
        self.link_engine = link_engine

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        kb_id = job.params.get("kb_id")
        node_id = job.params.get("node_id")

        if not kb_id or not node_id:
            raise ValueError("Missing kb_id or node_id in job params")

        ctx.emit_event("KGAddNodeStarted", {"kb_id": kb_id, "node_id": node_id})

        # Get the new node
        new_node = self.kg_repo.get_node(kb_id, node_id)
        if not new_node:
            raise ValueError(f"Node not found: {node_id}")

        # Recall candidates (most recent 20 nodes, excluding the new node itself)
        all_candidates = self.kg_repo.list_recent_nodes(kb_id, limit=21)
        candidates = [c for c in all_candidates if c["id"] != node_id][:20]

        if not candidates:
            logger.info(f"[KGAddNodeHandler] No candidates for node {node_id}")
            ctx.emit_event("KGAddNodeCompleted", {"edges_created": 0})
            return '{"edges_created": 0}'

        # Get blocked pairs
        blocked_pairs = self.kg_repo.get_deleted_pairs(kb_id)

        # Infer links using LLM
        inferred_links = self.link_engine.infer_links(
            new_node=new_node,
            candidates=candidates,
            blocked_pairs=blocked_pairs,
            max_links=5,
        )

        # Create edges
        edges_created = 0
        for link in inferred_links:
            try:
                self.kg_repo.upsert_edge(
                    kb_id=kb_id,
                    node_a=link.node_a_id,
                    node_b=link.node_b_id,
                    reason=link.reason,
                    reason_type="semantic",
                    created_by="system",
                    created_run_id=ctx.run_id,
                )
                edges_created += 1
                ctx.emit_event("EdgeCreated", {
                    "node_a": link.node_a_id,
                    "node_b": link.node_b_id,
                    "reason": link.reason,
                })
            except Exception as exc:
                logger.warning(f"[KGAddNodeHandler] Failed to create edge: {exc}")

        ctx.emit_event("KGAddNodeCompleted", {"edges_created": edges_created})
        logger.info(f"[KGAddNodeHandler] Created {edges_created} edges for node {node_id}")

        return f'{{"edges_created": {edges_created}}}'


class KGRelinkNodeHandler(JobHandler):
    """
    Handler for kg_relink_node jobs.

    Re-runs the auto-linking process for an existing node.
    Useful when user wants to refresh connections after graph changes.
    """

    def __init__(
        self,
        kg_repo: KBGraphRepository,
        link_engine: KGLinkEngine,
    ) -> None:
        self.kg_repo = kg_repo
        self.link_engine = link_engine

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        kb_id = job.params.get("kb_id")
        node_id = job.params.get("node_id")

        if not kb_id or not node_id:
            raise ValueError("Missing kb_id or node_id in job params")

        ctx.emit_event("KGRelinkNodeStarted", {"kb_id": kb_id, "node_id": node_id})

        # Get the node
        node = self.kg_repo.get_node(kb_id, node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        # Recall candidates
        all_candidates = self.kg_repo.list_recent_nodes(kb_id, limit=21)
        candidates = [c for c in all_candidates if c["id"] != node_id][:20]

        if not candidates:
            logger.info(f"[KGRelinkNodeHandler] No candidates for node {node_id}")
            ctx.emit_event("KGRelinkNodeCompleted", {"edges_created": 0})
            return '{"edges_created": 0}'

        # Get blocked pairs
        blocked_pairs = self.kg_repo.get_deleted_pairs(kb_id)

        # Infer links
        inferred_links = self.link_engine.infer_links(
            new_node=node,
            candidates=candidates,
            blocked_pairs=blocked_pairs,
            max_links=5,
        )

        # Create edges
        edges_created = 0
        for link in inferred_links:
            try:
                self.kg_repo.upsert_edge(
                    kb_id=kb_id,
                    node_a=link.node_a_id,
                    node_b=link.node_b_id,
                    reason=link.reason,
                    reason_type="semantic",
                    created_by="system",
                    created_run_id=ctx.run_id,
                )
                edges_created += 1
                ctx.emit_event("EdgeCreated", {
                    "node_a": link.node_a_id,
                    "node_b": link.node_b_id,
                    "reason": link.reason,
                })
            except Exception as exc:
                logger.warning(f"[KGRelinkNodeHandler] Failed to create edge: {exc}")

        ctx.emit_event("KGRelinkNodeCompleted", {"edges_created": edges_created})
        logger.info(f"[KGRelinkNodeHandler] Created {edges_created} edges for node {node_id}")

        return f'{{"edges_created": {edges_created}}}'
