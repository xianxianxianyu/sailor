from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas import FeedOut, ImportOPMLIn

router = APIRouter(prefix="/feeds", tags=["feeds"])


def mount_feed_routes(container: AppContainer) -> APIRouter:
    @router.post("/import-opml")
    def import_opml(payload: ImportOPMLIn) -> dict:
        from core.collector.opml_parser import parse_opml

        opml_path = Path(payload.opml_file) if payload.opml_file else container.settings.opml_file
        if not opml_path.exists():
            raise HTTPException(status_code=404, detail=f"OPML 文件不存在: {opml_path}")

        content = opml_path.read_text(encoding="utf-8")
        feed_infos = parse_opml(content)

        feeds_data = [
            {"name": f.name, "xml_url": f.xml_url, "html_url": f.html_url}
            for f in feed_infos
        ]
        imported = container.feed_repo.import_feeds(feeds_data)
        return {"imported": imported, "total_parsed": len(feed_infos)}

    @router.get("", response_model=list[FeedOut])
    def list_feeds() -> list[FeedOut]:
        feeds = container.feed_repo.list_feeds()
        return [FeedOut.model_validate(asdict(f)) for f in feeds]

    @router.patch("/{feed_id}")
    def toggle_feed(feed_id: str, enabled: bool = True) -> dict:
        container.feed_repo.toggle_enabled(feed_id, enabled)
        return {"feed_id": feed_id, "enabled": enabled}

    return router
