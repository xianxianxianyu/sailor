from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.container import AppContainer
from backend.app.schemas import AddKbItemIn, KbItemOut, KnowledgeBaseOut


router = APIRouter(prefix="/knowledge-bases", tags=["system"])

logger = logging.getLogger(__name__)


class CreateKBIn(BaseModel):
    name: str
    description: str | None = None


class KBItemResourceOut(BaseModel):
    resource_id: str
    title: str
    original_url: str
    summary: str
    topics: list[str]
    added_at: str


def mount_knowledge_base_routes(container: AppContainer) -> APIRouter:
    @router.get("", response_model=list[KnowledgeBaseOut])
    def list_knowledge_bases() -> list[KnowledgeBaseOut]:
        items = container.kb_repo.list_all()
        return [KnowledgeBaseOut.model_validate(asdict(item)) for item in items]

    @router.post("", response_model=KnowledgeBaseOut)
    def create_knowledge_base(payload: CreateKBIn) -> KnowledgeBaseOut:
        kb_id = f"kb_{hashlib.sha1(payload.name.encode()).hexdigest()[:8]}"
        try:
            kb = container.kb_repo.create_kb(kb_id, payload.name, payload.description)
        except Exception:
            raise HTTPException(status_code=409, detail="Knowledge base with this name already exists")
        return KnowledgeBaseOut.model_validate(asdict(kb))

    @router.delete("/{kb_id}")
    def delete_knowledge_base(kb_id: str) -> dict[str, bool]:
        # The kb_repo.delete_kb already handles cascade deletion of kb_items
        deleted = container.kb_repo.delete_kb(kb_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        return {"deleted": True}

    @router.post("/{kb_id}/items", response_model=KbItemOut)
    def add_kb_item(kb_id: str, payload: AddKbItemIn) -> KbItemOut:
        item = container.kb_repo.add_item(kb_id=kb_id, resource_id=payload.resource_id)

        # P11: 偏好反哺 — 收藏时增加该资源所有 tag 的 weight
        resource_tags = container.tag_repo.get_resource_tags(payload.resource_id)
        for tag in resource_tags:
            container.tag_repo.increment_weight(tag.tag_id)
        container.tag_repo.record_action(
            "add_to_kb", resource_id=payload.resource_id, kb_id=kb_id,
        )

        # P1: 触发自动连边 job
        import json
        import uuid
        from core.models import Job
        job_id = f"kg_add_{uuid.uuid4().hex[:12]}"
        job = Job(
            job_id=job_id,
            job_type="kg_add_node",
            input_json=json.dumps({"kb_id": kb_id, "node_id": payload.resource_id}),
        )
        container.job_repo.create_job(job)
        # job is queued; the worker process will execute it
        logger.info("[kb] Enqueued kg_add_node job %s", job_id)

        out = {**asdict(item), "kg_job_id": job_id}
        return KbItemOut.model_validate(out)

    @router.get("/{kb_id}/items", response_model=list[KBItemResourceOut])
    def list_kb_items(kb_id: str) -> list[KBItemResourceOut]:
        items = container.kb_repo.list_items(kb_id)
        result = []
        for item in items:
            resource = container.resource_repo.get_resource(item.resource_id)
            if resource:
                result.append(KBItemResourceOut(
                    resource_id=resource.resource_id,
                    title=resource.title,
                    original_url=resource.original_url,
                    summary=resource.summary,
                    topics=resource.topics,
                    added_at=item.added_at.isoformat(),
                ))
        return result

    @router.delete("/{kb_id}/items/{resource_id}")
    def remove_kb_item(kb_id: str, resource_id: str) -> dict[str, bool]:
        removed = container.kb_repo.remove_item(kb_id, resource_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"removed": True}

    return router
