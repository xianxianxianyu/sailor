from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from backend.app.container import AppContainer
from backend.app.schemas import KnowledgeBaseOut, ResourceOut


router = APIRouter(prefix="/resources", tags=["resources"])


def mount_resources_routes(container: AppContainer) -> APIRouter:
    @router.get("", response_model=list[ResourceOut])
    def list_resources(
        topic: str | None = Query(default=None),
        status: str = Query(default="all", pattern="^(all|inbox)$"),
    ) -> list[ResourceOut]:
        items = container.resource_repo.list_resources(topic=topic, status=status)
        return [ResourceOut.model_validate(asdict(item)) for item in items]

    @router.get("/{resource_id}", response_model=ResourceOut)
    def get_resource(resource_id: str) -> ResourceOut:
        item = container.resource_repo.get_resource(resource_id)
        if not item:
            raise HTTPException(status_code=404, detail="Resource not found")
        return ResourceOut.model_validate(asdict(item))

    @router.get("/{resource_id}/knowledge-bases", response_model=list[KnowledgeBaseOut])
    def list_resource_knowledge_bases(resource_id: str) -> list[KnowledgeBaseOut]:
        kbs = container.resource_repo.list_resource_kbs(resource_id)
        return [KnowledgeBaseOut.model_validate(asdict(kb)) for kb in kbs]

    return router
