from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from backend.app.container import AppContainer
from backend.app.utils import wait_for_job

router = APIRouter(prefix="/knowledge-bases", tags=["kg"])


class CreateEdgeIn(BaseModel):
    node_a_id: str
    node_b_id: str
    reason: str
    reason_type: str | None = None


def mount_kg_graph_routes(container: AppContainer) -> APIRouter:

    @router.get("/{kb_id}/graph")
    def get_graph(
        kb_id: str,
        mode: str = "full",
        start_node_id: str | None = None,
        depth: int = 2,
        limit: int = 200,
    ) -> dict:
        if mode == "local":
            if not start_node_id:
                raise HTTPException(
                    status_code=400, detail="start_node_id required for local mode"
                )
            nodes, edges = container.kb_graph_repo.get_subgraph(
                kb_id, start_node_id, depth
            )
            for e in edges:
                e["source"] = e["node_a_id"]
                e["target"] = e["node_b_id"]
            return {"nodes": nodes, "edges": edges, "mode": "local"}
        else:
            nodes = container.kb_graph_repo.list_nodes(kb_id, limit=limit)
            node_ids = {n["id"] for n in nodes}
            edges = container.kb_graph_repo.list_edges(kb_id, status="active")
            edges = [
                e
                for e in edges
                if e["node_a_id"] in node_ids and e["node_b_id"] in node_ids
            ]
            for e in edges:
                e["source"] = e["node_a_id"]
                e["target"] = e["node_b_id"]
            return {
                "nodes": nodes,
                "edges": edges,
                "mode": "full",
                "total_nodes": len(nodes),
            }

    @router.get("/{kb_id}/graph/nodes/{node_id}")
    def get_node(kb_id: str, node_id: str, page: int = 1, page_size: int = 50) -> dict:
        node = container.kb_graph_repo.get_node(kb_id, node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        neighbor_edges = container.kb_graph_repo.get_neighbors(kb_id, node_id)
        neighbors = []
        for edge in neighbor_edges:
            peer_id = edge["node_b_id"] if edge["node_a_id"] == node_id else edge["node_a_id"]
            peer = container.kb_graph_repo.get_node(kb_id, peer_id)
            if peer:
                neighbors.append({"node": peer, "edge": edge})

        total = len(neighbors)
        start = (page - 1) * page_size
        end = start + page_size
        neighbors_page = neighbors[start:end]

        return {
            "node": node,
            "neighbors": neighbors_page,
            "total_neighbors": total,
            "page": page,
            "page_size": page_size,
        }

    @router.post("/{kb_id}/graph/edges")
    def create_edge(kb_id: str, payload: CreateEdgeIn) -> dict:
        return container.kb_graph_repo.upsert_edge(
            kb_id,
            payload.node_a_id,
            payload.node_b_id,
            payload.reason,
            payload.reason_type,
            created_by="user",
        )

    @router.delete("/{kb_id}/graph/edges/{node_a_id}/{node_b_id}")
    def delete_edge(kb_id: str, node_a_id: str, node_b_id: str) -> dict:
        ok = container.kb_graph_repo.soft_delete_edge(kb_id, node_a_id, node_b_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Edge not found or already deleted")
        return {"deleted": True}

    @router.post("/{kb_id}/graph/edges/{node_a_id}/{node_b_id}/freeze")
    def freeze_edge(kb_id: str, node_a_id: str, node_b_id: str) -> dict:
        container.kb_graph_repo.freeze_edge(kb_id, node_a_id, node_b_id)
        return {"frozen": True}

    @router.post("/{kb_id}/graph/edges/{node_a_id}/{node_b_id}/unfreeze")
    def unfreeze_edge(kb_id: str, node_a_id: str, node_b_id: str) -> dict:
        container.kb_graph_repo.unfreeze_edge(kb_id, node_a_id, node_b_id)
        return {"frozen": False}

    @router.post("/{kb_id}/graph/nodes/{node_id}/relink")
    def relink_node(
        kb_id: str,
        node_id: str,
        response: Response,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> dict:
        """Trigger auto-linking job for an existing node."""
        from core.models import Job
        job_id = f"kg_relink_{uuid.uuid4().hex[:12]}"
        job = Job(
            job_id=job_id,
            job_type="kg_relink_node",
            input_json=json.dumps({"kb_id": kb_id, "node_id": node_id}),
        )
        container.job_repo.create_job(job)

        if not wait:
            return {"job_id": job_id, "status": "queued"}

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
        payload = {"job_id": job_id, "status": result_job.status}
        if result_job.status == "failed":
            payload["error_message"] = result_job.error_message or "kg_relink_node failed"
        return payload

    @router.get("/{kb_id}/graph/history")
    def get_graph_history(kb_id: str, limit: int = 50) -> dict:
        """Get recent auto-linking job history."""
        # Fetch a wider window then filter (JobRepository.list_jobs does not support multi-type filter).
        fetch_limit = max(limit * 20, 200)
        fetch_limit = min(fetch_limit, 1000)
        jobs = container.job_repo.list_jobs(limit=fetch_limit)
        # Filter by kb_id
        kb_jobs = [j for j in jobs if j.job_type in ("kg_add_node", "kg_relink_node") and j.params.get("kb_id") == kb_id]
        kb_jobs = kb_jobs[:limit]
        return {"jobs": [
            {
                "job_id": j.job_id,
                "job_type": j.job_type,
                "status": j.status,
                "node_id": j.params.get("node_id"),
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                "output": j.output_json,
            }
            for j in kb_jobs
        ]}

    return router
