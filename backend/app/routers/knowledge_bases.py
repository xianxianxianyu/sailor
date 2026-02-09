from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from backend.app.container import AppContainer
from backend.app.schemas import AddKbItemIn, KbItemOut, KnowledgeBaseOut


router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


def mount_knowledge_base_routes(container: AppContainer) -> APIRouter:
    @router.get("", response_model=list[KnowledgeBaseOut])
    def list_knowledge_bases() -> list[KnowledgeBaseOut]:
        items = container.kb_repo.list_all()
        return [KnowledgeBaseOut.model_validate(asdict(item)) for item in items]

    @router.post("/{kb_id}/items", response_model=KbItemOut)
    def add_kb_item(kb_id: str, payload: AddKbItemIn) -> KbItemOut:
        item = container.kb_repo.add_item(kb_id=kb_id, resource_id=payload.resource_id)
        return KbItemOut.model_validate(asdict(item))

    return router
