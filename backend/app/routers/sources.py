from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.request import Request, urlopen

import feedparser
from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.routers.logs import add_log
from backend.app.schemas import (
    CreateSourceIn,
    ImportSourcesIn,
    ImportSourcesOut,
    RunSourceOut,
    SourceOut,
    SourceRunOut,
    SourceStatusOut,
    UpdateSourceIn,
)
from core.models import RawEntry, SourceRecord

router = APIRouter(prefix="/sources", tags=["sources"])


def mount_source_routes(container: AppContainer) -> APIRouter:
    @router.get("", response_model=list[SourceOut])
    def list_sources(source_type: str | None = None, enabled_only: bool = False) -> list[SourceOut]:
        sources = container.source_repo.list_sources(source_type=source_type, enabled_only=enabled_only)
        return [SourceOut.model_validate(asdict(s)) for s in sources]

    @router.post("", response_model=SourceOut)
    def create_source(payload: CreateSourceIn) -> SourceOut:
        endpoint = payload.endpoint
        source_id = payload.source_id or _make_source_id(payload.source_type, endpoint, payload.name)
        source = SourceRecord(
            source_id=source_id,
            source_type=payload.source_type,
            name=payload.name,
            endpoint=endpoint,
            config=payload.config,
            enabled=payload.enabled,
            schedule_minutes=max(payload.schedule_minutes, 1),
        )
        created = container.source_repo.upsert_source(source)
        return SourceOut.model_validate(asdict(created))

    @router.patch("/{source_id}", response_model=SourceOut)
    def update_source(source_id: str, payload: UpdateSourceIn) -> SourceOut:
        updated = container.source_repo.update_source(
            source_id,
            name=payload.name,
            endpoint=payload.endpoint,
            config=payload.config,
            enabled=payload.enabled,
            schedule_minutes=max(payload.schedule_minutes, 1) if payload.schedule_minutes is not None else None,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Source not found")
        return SourceOut.model_validate(asdict(updated))

    @router.delete("/{source_id}")
    def delete_source(source_id: str) -> dict[str, bool]:
        deleted = container.source_repo.delete_source(source_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Source not found")
        return {"deleted": True}

    @router.get("/status", response_model=SourceStatusOut)
    def source_status() -> SourceStatusOut:
        return SourceStatusOut.model_validate(container.source_repo.get_status_summary())

    @router.get("/{source_id}/runs", response_model=list[SourceRunOut])
    def list_runs(source_id: str, limit: int = 20) -> list[SourceRunOut]:
        runs = container.source_repo.list_runs(source_id, limit=max(1, min(limit, 200)))
        return [SourceRunOut.model_validate(asdict(run)) for run in runs]

    @router.post("/import-local", response_model=ImportSourcesOut)
    def import_local_config(payload: ImportSourcesIn) -> ImportSourcesOut:
        config_path = _resolve_config_path(container, payload.config_file)
        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")

        add_log("INFO", f"[sources] 开始导入本地配置: {config_path}")
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"配置文件 JSON 无效: {exc}") from exc

        defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
        source_items = data.get("sources")
        if not isinstance(source_items, list):
            raise HTTPException(status_code=400, detail="配置文件必须包含 sources 数组")

        imported = 0
        rss_rows: list[dict[str, Any]] = []
        for item in source_items:
            if not isinstance(item, dict):
                continue

            source_type = str(item.get("source_type") or defaults.get("source_type") or "rss")
            endpoint = item.get("endpoint") or item.get("xml_url") or item.get("url")
            endpoint = str(endpoint) if endpoint else None
            name = str(item.get("name") or endpoint or "Unnamed Source")
            source_id = str(item.get("source_id") or _make_source_id(source_type, endpoint, name))

            schedule_raw = item.get("schedule_minutes", item.get("poll_minutes", defaults.get("poll_minutes", 30)))
            schedule_minutes = max(_coerce_int(schedule_raw, 30), 1)
            enabled = bool(item.get("enabled", defaults.get("enabled", True)))

            config = dict(item.get("config") or {})
            for key in ("xml_url", "html_url", "url", "tags", "poll_minutes", "schedule_minutes"):
                if key in item and key not in config:
                    config[key] = item[key]

            container.source_repo.upsert_source(
                SourceRecord(
                    source_id=source_id,
                    source_type=source_type,
                    name=name,
                    endpoint=endpoint,
                    config=config,
                    enabled=enabled,
                    schedule_minutes=schedule_minutes,
                )
            )
            imported += 1

            if source_type == "rss":
                xml_url = str(item.get("xml_url") or endpoint or "")
                if xml_url:
                    rss_rows.append(
                        {
                            "name": name,
                            "xml_url": xml_url,
                            "html_url": str(item.get("html_url")) if item.get("html_url") else None,
                        }
                    )

        rss_synced = container.feed_repo.import_feeds(rss_rows) if rss_rows else 0
        add_log("INFO", f"[sources] 导入完成: 导入 {imported} 个 source, 同步 {rss_synced} 个 RSS feed")
        return ImportSourcesOut(imported=imported, rss_synced=rss_synced, total_parsed=len(source_items))

    @router.post("/{source_id}/run", response_model=RunSourceOut)
    def run_source(source_id: str) -> RunSourceOut:
        source = container.source_repo.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        add_log("INFO", f"[sources] 开始运行 source: {source_id} ({source.name})")
        run = container.source_repo.create_run(source_id)
        try:
            entries = _collect_source_entries(source, container)
            add_log("INFO", f"[sources] 获取 {len(entries)} 条原始条目")
            processed = 0
            for entry in entries:
                resource = container.ingestion_service.pipeline.process(entry)
                container.resource_repo.upsert(resource)
                container.source_repo.upsert_item_index(
                    source_id=source.source_id,
                    item_key=entry.entry_id,
                    canonical_url=resource.canonical_url,
                    resource_id=resource.resource_id,
                )
                processed += 1

            container.source_repo.finish_run(
                run.run_id,
                status="success",
                fetched_count=len(entries),
                processed_count=processed,
                metadata={"source_type": source.source_type},
            )
            add_log("INFO", f"[sources] 完成 source: {source_id}, 获取 {len(entries)} 条, 处理 {processed} 条")
            return RunSourceOut(
                run_id=run.run_id,
                source_id=source.source_id,
                status="success",
                fetched_count=len(entries),
                processed_count=processed,
            )
        except Exception as exc:
            container.source_repo.finish_run(
                run.run_id,
                status="failed",
                fetched_count=0,
                processed_count=0,
                error_message=str(exc)[:500],
                metadata={"source_type": source.source_type},
            )
            add_log("ERROR", f"[sources] source: {source_id} 失败: {exc}")
            raise HTTPException(status_code=500, detail=f"Source run failed: {exc}") from exc

    return router


def _resolve_config_path(container: AppContainer, config_file: str | None) -> Path:
    base_dir = container.settings.opml_file.parent
    chosen = Path(config_file) if config_file else Path("SailorRSSConfig.json")
    if chosen.is_absolute():
        return chosen
    return (base_dir / chosen).resolve()


def _make_source_id(source_type: str, endpoint: str | None, name: str) -> str:
    key = f"{source_type}:{endpoint or ''}:{name}".encode("utf-8")
    return "src_" + hashlib.sha256(key).hexdigest()[:12]


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _collect_source_entries(source: SourceRecord, container: AppContainer) -> list[RawEntry]:
    if source.source_type == "rss":
        return _collect_rss_entries(source)
    if source.source_type == "web_page":
        return _collect_web_entries(source)
    if source.source_type == "manual_file":
        return _collect_manual_entries(source, container.settings.opml_file.parent)

    raise ValueError(f"Unsupported source_type: {source.source_type}")


def _collect_rss_entries(source: SourceRecord) -> list[RawEntry]:
    xml_url = source.endpoint or str(source.config.get("xml_url") or "")
    if not xml_url:
        raise ValueError("RSS source requires xml_url or endpoint")

    parsed = feedparser.parse(xml_url)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise ValueError(f"RSS parse failed: {getattr(parsed, 'bozo_exception', 'unknown')} ")

    entries: list[RawEntry] = []
    for entry in parsed.entries:
        link = getattr(entry, "link", None)
        if not link:
            continue
        entry_id = str(getattr(entry, "id", None) or link)
        title = str(getattr(entry, "title", None) or "(untitled)")

        content = ""
        content_block = getattr(entry, "content", None)
        if content_block:
            first = content_block[0] if isinstance(content_block, list) and content_block else content_block
            content = str(getattr(first, "value", None) or "")
        if not content:
            content = str(getattr(entry, "summary", None) or "")

        published_at = None
        for attr in ("published", "updated"):
            val = getattr(entry, attr, None)
            if val:
                published_at = _parse_datetime(str(val))
                break

        entries.append(
            RawEntry(
                entry_id=entry_id,
                feed_id=source.source_id,
                source=source.source_type,
                title=title,
                url=str(link),
                content=content,
                published_at=published_at,
            )
        )
    return entries


def _collect_web_entries(source: SourceRecord) -> list[RawEntry]:
    urls = source.config.get("urls")
    if isinstance(urls, list):
        targets = [str(u) for u in urls if isinstance(u, str) and u]
    else:
        targets = []
    if not targets and source.endpoint:
        targets = [source.endpoint]
    if not targets:
        raise ValueError("web_page source requires endpoint or config.urls")

    user_agent = str(source.config.get("user_agent") or "SailorSourceCollector/1.0")
    entries: list[RawEntry] = []
    for url in targets:
        request = Request(url, headers={"User-Agent": user_agent})
        with urlopen(request, timeout=20) as response:
            html = response.read().decode("utf-8", errors="ignore")
        title = _extract_title(html) or url
        entry_id = "web_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        entries.append(
            RawEntry(
                entry_id=entry_id,
                feed_id=source.source_id,
                source=source.source_type,
                title=title,
                url=url,
                content=html,
                published_at=None,
            )
        )
    return entries


def _collect_manual_entries(source: SourceRecord, base_dir: Path) -> list[RawEntry]:
    path_value = source.endpoint or str(source.config.get("path") or "")
    if not path_value:
        raise ValueError("manual_file source requires endpoint or config.path")

    source_path = Path(path_value)
    if not source_path.is_absolute():
        source_path = (base_dir / source_path).resolve()
    if not source_path.exists():
        raise ValueError(f"manual_file path does not exist: {source_path}")

    data = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        candidates = data.get("entries")
    else:
        candidates = data
    if not isinstance(candidates, list):
        raise ValueError("manual_file content must be an array or {entries:[...]} object")

    entries: list[RawEntry] = []
    for idx, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url:
            continue
        title = str(item.get("title") or url)
        content = str(item.get("content") or "")
        entry_id = str(item.get("entry_id") or f"manual_{source.source_id}_{idx}")
        published_at = _parse_datetime(item.get("published_at")) if item.get("published_at") else None
        entries.append(
            RawEntry(
                entry_id=entry_id,
                feed_id=source.source_id,
                source=source.source_type,
                title=title,
                url=url,
                content=content,
                published_at=published_at,
            )
        )
    return entries


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title or None
