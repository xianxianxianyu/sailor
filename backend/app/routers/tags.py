from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas import CreateTagIn, TagOut, UpdateTagIn


router = APIRouter(prefix="/tags", tags=["tags"])


def mount_tag_routes(container: AppContainer) -> APIRouter:
    @router.get("", response_model=list[TagOut])
    def list_tags() -> list[TagOut]:
        tags = container.tag_repo.list_tags()
        return [TagOut.model_validate(asdict(t)) for t in tags]

    @router.post("", response_model=TagOut)
    def create_tag(payload: CreateTagIn) -> TagOut:
        tag = container.tag_repo.create_tag(name=payload.name, color=payload.color)
        return TagOut.model_validate(asdict(tag))

    @router.put("/{tag_id}", response_model=TagOut)
    def update_tag(tag_id: str, payload: UpdateTagIn) -> TagOut:
        tag = container.tag_repo.update_tag(tag_id, name=payload.name, color=payload.color)
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        return TagOut.model_validate(asdict(tag))

    @router.delete("/{tag_id}")
    def delete_tag(tag_id: str) -> dict[str, bool]:
        deleted = container.tag_repo.delete_tag(tag_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Tag not found")
        return {"deleted": True}

    @router.get("/{tag_id}/resources", response_model=list[str])
    def get_tag_resources(tag_id: str) -> list[str]:
        return container.tag_repo.get_resources_by_tag(tag_id)

    @router.post("/resource/{resource_id}/{tag_id}")
    def tag_resource(resource_id: str, tag_id: str) -> dict[str, str]:
        container.tag_repo.tag_resource(resource_id, tag_id, source="manual")
        container.tag_repo.increment_weight(tag_id)
        container.tag_repo.record_action("tag_resource", resource_id=resource_id, tag_id=tag_id)
        return {"status": "ok"}

    @router.get("/resource/{resource_id}", response_model=list[TagOut])
    def get_resource_tags(resource_id: str) -> list[TagOut]:
        tags = container.tag_repo.get_resource_tags(resource_id)
        return [TagOut.model_validate(asdict(t)) for t in tags]

    return router
