from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import feedparser
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.container import AppContainer
from backend.app.schemas import FeedOut, ImportOPMLIn, RunFeedOut

logger = logging.getLogger("sailor")

router = APIRouter(prefix="/feeds", tags=["feeds"])


class AddFeedIn(BaseModel):
    name: str
    xml_url: str
    html_url: str | None = None


def mount_feed_routes(container: AppContainer) -> APIRouter:
    @router.get("", response_model=list[FeedOut])
    def list_feeds() -> list[FeedOut]:
        feeds = container.feed_repo.list_feeds()
        logger.info(f"获取订阅源列表: {len(feeds)} 个")
        return [FeedOut.model_validate(asdict(f)) for f in feeds]

    @router.post("", response_model=FeedOut)
    def add_feed(payload: AddFeedIn) -> FeedOut:
        logger.info(f"添加订阅源: {payload.name} ({payload.xml_url})")
        feed = container.feed_repo.add_feed(payload.name, payload.xml_url, payload.html_url)
        logger.info(f"✅ 订阅源添加成功: {feed.id}")
        return FeedOut.model_validate(asdict(feed))

    @router.delete("/{feed_id}")
    def delete_feed(feed_id: str) -> dict[str, bool]:
        logger.info(f"删除订阅源: {feed_id}")
        deleted = container.feed_repo.delete_feed(feed_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Feed not found")
        logger.info(f"✅ 订阅源已删除: {feed_id}")
        return {"deleted": True}

    @router.patch("/{feed_id}")
    def toggle_feed(feed_id: str, enabled: bool = True) -> dict:
        logger.info(f"{'启用' if enabled else '禁用'}订阅源: {feed_id}")
        container.feed_repo.toggle_enabled(feed_id, enabled)
        return {"feed_id": feed_id, "enabled": enabled}

    @router.post("/{feed_id}/run", response_model=RunFeedOut)
    def run_feed(feed_id: str) -> RunFeedOut:
        feeds = container.feed_repo.list_feeds()
        feed = next((f for f in feeds if f.feed_id == feed_id), None)
        if not feed:
            raise HTTPException(status_code=404, detail="Feed not found")

        logger.info(f"[feeds] 开始运行 feed: {feed_id} ({feed.name})")

        try:
            # 解析 RSS
            parsed = feedparser.parse(feed.xml_url)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise ValueError(f"RSS parse failed: {getattr(parsed, 'bozo_exception', 'unknown')}")

            entries = parsed.entries
            logger.info(f"[feeds] 获取 {len(entries)} 条原始条目")

            processed = 0
            for entry in entries:
                try:
                    # 构建 RawEntry
                    from core.models import RawEntry

                    link = getattr(entry, "link", None) or ""
                    title = getattr(entry, "title", "无标题")
                    published = getattr(entry, "published", None) or getattr(entry, "updated", None)
                    summary = getattr(entry, "summary", "") or getattr(entry, "description", "")

                    raw_entry = RawEntry(
                        entry_id=link or f"{feed.name}:{title}",
                        source=feed.name,
                        url=link,
                        title=title,
                        published=published,
                        content=summary,
                    )

                    # 处理并入库
                    resource = container.ingestion_service.pipeline.process(raw_entry)
                    container.resource_repo.upsert(resource)
                    processed += 1
                except Exception:
                    logger.exception(f"[feeds] 处理条目失败: {getattr(entry, 'link', 'unknown')}")
                    continue

            # 更新 feed 状态
            container.feed_repo.update_feed_status(
                feed_id=feed_id,
                last_fetched_at=datetime.now(),
                error_count=0,
                last_error=None,
            )

            logger.info(f"[feeds] 完成 feed: {feed_id}, 获取 {len(entries)} 条, 处理 {processed} 条")
            return RunFeedOut(
                feed_id=feed_id,
                status="success",
                fetched_count=len(entries),
                processed_count=processed,
            )

        except Exception as e:
            logger.exception(f"[feeds] 运行 feed 失败: {feed_id}")
            container.feed_repo.update_feed_status(
                feed_id=feed_id,
                last_fetched_at=datetime.now(),
                error_count=(feed.error_count or 0) + 1,
                last_error=str(e),
            )
            raise HTTPException(status_code=500, detail=f"Run failed: {str(e)}")

    @router.post("/import-opml")
    def import_opml(payload: ImportOPMLIn) -> dict:
        from core.collector.opml_parser import parse_opML

        logger.info("📥 开始导入 OPML 文件...")
        opml_path = Path(payload.opml_file) if payload.opml_file else container.settings.opml_file
        if not opml_path.exists():
            logger.error(f"❌ OPML 文件不存在: {opml_path}")
            raise HTTPException(status_code=404, detail=f"OPML 文件不存在: {opml_path}")

        content = opml_path.read_text(encoding="utf-8")
        feed_infos = parse_opml(content)
        logger.info(f"📄 解析到 {len(feed_infos)} 个订阅源")

        feeds_data = [
            {"name": f.name, "xml_url": f.xml_url, "html_url": f.html_url}
            for f in feed_infos
        ]
        imported = container.feed_repo.import_feeds(feeds_data)
        logger.info(f"✅ 成功导入 {imported}/{len(feed_infos)} 个订阅源")
        return {"imported": imported, "total_parsed": len(feed_infos)}

    @router.get("/source-status")
    def source_status() -> dict:
        feeds = container.feed_repo.list_feeds()
        enabled = sum(1 for f in feeds if f.enabled)
        errored = sum(1 for f in feeds if f.error_count > 0)
        miniflux_ok = bool(container.settings.miniflux_base_url and container.settings.miniflux_token)
        seed_exists = container.settings.seed_file.exists()
        logger.info(f"📊 订阅源状态: 总计 {len(feeds)}, 启用 {enabled}, 错误 {errored}")
        return {
            "rss_total": len(feeds),
            "rss_enabled": enabled,
            "rss_errored": errored,
            "miniflux_configured": miniflux_ok,
            "seed_file_exists": seed_exists,
        }

    return router
