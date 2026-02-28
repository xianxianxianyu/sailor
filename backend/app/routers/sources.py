from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import logging
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
    RunBatchOut,
    RunSourceOut,
    SourceOut,
    SourceResourceOut,
    SourceRunOut,
    SourceStatusOut,
    UpdateSourceIn,
)
from core.models import RawEntry, SourceRecord

logger = logging.getLogger("sailor")
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

    @router.post("/run-by-type/{source_type}", response_model=RunBatchOut)
    def run_sources_by_type(source_type: str, enabled_only: bool = True) -> RunBatchOut:
        """按类型批量运行所有源"""
        sources = container.source_repo.list_sources(source_type=source_type, enabled_only=enabled_only)
        if not sources:
            raise HTTPException(status_code=404, detail=f"No sources found for type: {source_type}")

        add_log("INFO", f"[sources] 开始批量运行 source_type={source_type}, 共 {len(sources)} 个源")

        success_count = 0
        failed_count = 0
        total_fetched = 0
        total_processed = 0

        for source in sources:
            try:
                entries = _collect_source_entries(source, container)
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

                success_count += 1
                total_fetched += len(entries)
                total_processed += processed
                add_log("INFO", f"[sources] source={source.name} 完成, 获取 {len(entries)} 条")

            except Exception as e:
                failed_count += 1
                add_log("ERROR", f"[sources] source={source.name} 失败: {e}")

        add_log("INFO", f"[sources] 批量运行完成: 成功 {success_count}, 失败 {failed_count}, 共获取 {total_fetched} 条")

        return RunBatchOut(
            source_type=source_type,
            total_sources=len(sources),
            success_count=success_count,
            failed_count=failed_count,
            total_fetched=total_fetched,
            total_processed=total_processed,
        )

    @router.get("/{source_id}/resources", response_model=list[SourceResourceOut])
    def get_source_resources(source_id: str, limit: int = 50, offset: int = 0) -> list[SourceResourceOut]:
        """获取统一源的最近抓取内容"""
        from backend.app.routers.logs import add_log
        add_log("INFO", f"[sources] get_source_resources called: source_id={source_id}, limit={limit}")
        items = container.source_repo.list_source_resources(source_id, limit, offset)
        add_log("INFO", f"[sources] list_source_resources returned {len(items)} items for source_id={source_id}")
        result = []
        for item in items:
            result.append(SourceResourceOut(
                resource_id=item.resource_id,
                canonical_url=item.canonical_url,
                source=item.source,
                title=item.title,
                published_at=item.published_at,
                text=item.text,
                original_url=item.original_url,
                topics=item.topics,
                summary=item.summary,
                last_seen_at=item.last_seen_at,
            ))
        return result

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
    if source.source_type == "atom":
        return _collect_atom_entries(source)
    if source.source_type == "jsonfeed":
        return _collect_jsonfeed_entries(source)
    if source.source_type == "web_page":
        return _collect_web_entries(source)
    if source.source_type == "manual_file":
        return _collect_manual_entries(source, container.settings.opml_file.parent)
    if source.source_type == "academic_api":
        return _collect_academic_entries(source)
    if source.source_type == "api":
        return _collect_api_entries(source)
    if source.source_type == "site_map":
        return _collect_sitemap_entries(source)
    if source.source_type == "api_json":
        return _collect_api_json_entries(source)
    if source.source_type == "api_xml":
        return _collect_api_xml_entries(source)
    if source.source_type == "opml":
        return _collect_opml_entries(source, container.settings.opml_file.parent)
    if source.source_type == "jsonl":
        return _collect_jsonl_entries(source, container.settings.opml_file.parent)

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
                source=source.name,
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


def _collect_academic_entries(source: SourceRecord) -> list[RawEntry]:
    """采集学术 API 源（arXiv 等）"""
    config = source.config
    platform = config.get("platform", "arxiv")

    if platform == "arxiv":
        from core.collector.arxiv_engine import ArxivCollector
        collector = ArxivCollector(config)
        return collector.collect()

    raise ValueError(f"Unsupported academic platform: {platform}")


def _collect_api_entries(source: SourceRecord) -> list[RawEntry]:
    """采集 API 源（掘金等）"""
    config = source.config
    platform = config.get("platform", "juejin")

    if platform == "juejin":
        return _collect_juejin_entries(source.endpoint or "", config)

    raise ValueError(f"Unsupported API platform: {platform}")


def _collect_juejin_entries(endpoint: str, config: dict) -> list[RawEntry]:
    """采集掘金文章"""
    import requests

    url = "https://api.juejin.cn/content_api/v1/article/query_list"
    payload = {
        "sort_type": 300,  # 热门
        "cursor": "0",
        "cate_id": config.get("category_id", "")
    }

    response = requests.post(url, json=payload, timeout=20)
    data = response.json()

    entries = []
    for item in data.get("data", [])[:config.get("max_results", 20)]:
        article_info = item.get("article_info", {})
        entries.append(RawEntry(
            entry_id=article_info.get("article_id", ""),
            feed_id="juejin",
            source="juejin",
            title=article_info.get("title", ""),
            url=f"https://juejin.cn/post/{article_info.get('article_id', '')}",
            content=article_info.get("mark_content", ""),
            published_at=datetime.fromtimestamp(article_info.get("ctime", 0)) if article_info.get("ctime") else None,
        ))
    return entries


def _collect_sitemap_entries(source: SourceRecord) -> list[RawEntry]:
    """采集站点地图 XML"""
    import xml.etree.ElementTree as ET

    xml_url = source.endpoint
    if not xml_url:
        raise ValueError("site_map source requires endpoint (URL)")

    user_agent = str(source.config.get("user_agent") or "SailorSourceCollector/1.0")
    request = Request(xml_url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=20) as response:
        xml_content = response.read().decode("utf-8", errors="ignore")

    entries = []
    try:
        root = ET.fromstring(xml_content)
        # 处理 XML 命名空间
        namespaces = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                     'xhtml': 'http://www.w3.org/1999/xhtml'}

        for url_elem in root.findall('.//sm:url', namespaces) or root.findall('.//url'):
            loc = url_elem.find('sm:loc', namespaces) or url_elem.find('loc')
            if loc is None or not loc.text:
                continue

            url = loc.text
            entry_id = "sitemap_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

            # 尝试获取标题（从 xhtml:link 或从 URL 推断）
            title = url.split('/')[-1] or url
            link_elem = url_elem.find('xhtml:link', namespaces)
            if link_elem is not None and link_elem.get('title'):
                title = link_elem.get('title')

            # 获取最后修改时间
            lastmod = url_elem.find('sm:lastmod', namespaces) or url_elem.find('lastmod')
            published_at = _parse_datetime(lastmod.text) if lastmod is not None and lastmod.text else None

            entries.append(RawEntry(
                entry_id=entry_id,
                feed_id=source.source_id,
                source=source.source_type,
                title=title,
                url=url,
                content="",
                published_at=published_at,
            ))
    except ET.ParseError as exc:
        raise ValueError(f"Failed to parse sitemap XML: {exc}") from exc

    return entries


def _collect_api_json_entries(source: SourceRecord) -> list[RawEntry]:
    """采集 API JSON 源"""
    import requests

    api_url = source.endpoint
    if not api_url:
        raise ValueError("api_json source requires endpoint (URL)")

    user_agent = str(source.config.get("user_agent") or "SailorSourceCollector/1.0")
    headers = {"User-Agent": user_agent}

    # 支持自定义请求头和 HTTP 方法
    custom_headers = source.config.get("headers", {})
    if isinstance(custom_headers, dict):
        headers.update(custom_headers)

    method = source.config.get("method", "GET").upper()
    timeout = int(source.config.get("timeout", 20))

    request_kwargs = {"headers": headers, "timeout": timeout}

    # 处理请求体
    if method == "POST":
        request_kwargs["data"] = source.config.get("body", "").encode("utf-8")
        request_kwargs["headers"]["Content-Type"] = source.config.get("content_type", "application/json")

    request = Request(api_url, **request_kwargs)
    with urlopen(request, timeout=timeout) as response:
        json_data = json.loads(response.read().decode("utf-8", errors="ignore"))

    # 支持配置 JSONPath 来提取条目数组
    items_path = source.config.get("items_path", "").split(".") if source.config.get("items_path") else None

    if items_path:
        data = json_data
        for key in items_path:
            if data is None:
                break
            data = data.get(key) if isinstance(data, dict) else (data[int(key)] if isinstance(data, list) and key.isdigit() else None)
        items = data if isinstance(data, list) else [data]
    else:
        items = json_data if isinstance(json_data, list) else [json_data]

    entries = []
    max_results = source.config.get("max_results", 20)

    for idx, item in enumerate(items[:max_results]):
        if not isinstance(item, dict):
            continue

        # 支持自定义字段映射
        url_field = source.config.get("url_field", "url")
        title_field = source.config.get("title_field", "title")
        content_field = source.config.get("content_field", "content")
        id_field = source.config.get("id_field", "id")

        entry_id = str(item.get(id_field, f"api_json_{source.source_id}_{idx}"))
        url = str(item.get(url_field, ""))
        title = str(item.get(title_field, url))
        content = str(item.get(content_field, ""))

        # 解析时间字段
        published_at = None
        if source.config.get("published_at_field"):
            published_at = _parse_datetime(item.get(source.config.get("published_at_field")))

        entries.append(RawEntry(
            entry_id=entry_id,
            feed_id=source.source_id,
            source=source.source_type,
            title=title,
            url=url,
            content=content,
            published_at=published_at,
        ))

    return entries


# === 新增源类型收集器 ===

def _collect_atom_entries(source: SourceRecord) -> list[RawEntry]:
    """采集 Atom 订阅源"""
    import feedparser

    xml_url = source.endpoint or str(source.config.get("xml_url") or "")
    if not xml_url:
        raise ValueError("Atom source requires xml_url or endpoint")

    parsed = feedparser.parse(xml_url)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise ValueError(f"Atom parse failed: {getattr(parsed, 'bozo_exception', 'unknown')}")

    entries: list[RawEntry] = []
    for entry in parsed.entries:
        link = getattr(entry, "link", None) or ""
        title = getattr(entry, "title", "无标题")
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
        published = getattr(entry, "published", None) or getattr(entry, "updated", None)

        entries.append(RawEntry(
            entry_id=link or f"{source.name}:{title}",
            feed_id=source.source_id,
            source=source.name,
            url=link,
            title=title,
            content=summary,
            published_at=published,
        ))

    logger.info(f"[sources] atom collected {len(entries)} entries from {source.name}")
    return entries


def _collect_jsonfeed_entries(source: SourceRecord) -> list[RawEntry]:
    """采集 JSON Feed 源"""
    import requests

    json_url = source.endpoint or str(source.config.get("url") or "")
    if not json_url:
        raise ValueError("JSON Feed source requires endpoint (URL)")

    user_agent = str(source.config.get("user_agent") or "SailorSourceCollector/1.0")
    headers = {"User-Agent": user_agent}

    response = requests.get(json_url, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()

    items = data.get("items", []) or data.get("attachments", []) or []

    # 如果是 JSON Feed 规范
    if "title" in data and "items" in data:
        items = data.get("items", [])

    entries = []
    for idx, item in enumerate(items):
        url = item.get("url", item.get("id", ""))
        title = item.get("title", url)
        content = item.get("content_html") or item.get("content_text") or item.get("summary", "")
        published = item.get("date_published", item.get("updated"))

        entries.append(RawEntry(
            entry_id=item.get("id", f"jsonfeed_{source.source_id}_{idx}"),
            feed_id=source.source_id,
            source=source.name,
            url=url,
            title=title,
            content=content,
            published_at=published,
        ))

    logger.info(f"[sources] jsonfeed collected {len(entries)} entries from {source.name}")
    return entries


def _collect_api_xml_entries(source: SourceRecord) -> list[RawEntry]:
    """采集 API XML 源"""
    import xml.etree.ElementTree as ET

    api_url = source.endpoint
    if not api_url:
        raise ValueError("api_xml source requires endpoint (URL)")

    user_agent = str(source.config.get("user_agent") or "SailorSourceCollector/1.0")
    headers = {"User-Agent": user_agent}

    import requests
    response = requests.get(api_url, headers=headers, timeout=20)
    response.raise_for_status()

    # 解析 XML
    root = ET.fromstring(response.content)

    # 支持配置 XML 路径来提取条目数组
    items_path = source.config.get("items_path", "").split("/") if source.config.get("items_path") else None

    if items_path:
        data = root
        for key in items_path:
            data = data.find(key) if data is not None else None
        items = list(data) if data is not None else []
    else:
        items = list(root)

    # 字段映射配置
    url_field = source.config.get("url_field", "url")
    title_field = source.config.get("title_field", "title")
    content_field = source.config.get("content_field", "description")
    id_field = source.config.get("id_field", "id")

    entries = []
    max_results = source.config.get("max_results", 20)

    for idx, item in enumerate(items[:max_results]):
        # item 可以是 Element 或 dict
        if hasattr(item, "find"):  # Element
            entry_id = item.find(id_field).text if item.find(id_field) is not None else f"api_xml_{source.source_id}_{idx}"
            url = item.find(url_field).text if item.find(url_field) is not None else ""
            title = item.find(title_field).text if item.find(title_field) is not None else url
            content = item.find(content_field).text if item.find(content_field) is not None else ""
        else:  # dict
            entry_id = str(item.get(id_field, f"api_xml_{source.source_id}_{idx}"))
            url = str(item.get(url_field, ""))
            title = str(item.get(title_field, url))
            content = str(item.get(content_field, ""))

        entries.append(RawEntry(
            entry_id=entry_id,
            feed_id=source.source_id,
            source=source.name,
            url=url,
            title=title,
            content=content,
            published_at=None,
        ))

    logger.info(f"[sources] api_xml collected {len(entries)} entries from {source.name}")
    return entries


def _collect_opml_entries(source: SourceRecord, base_dir: Path) -> list[RawEntry]:
    """从 OPML 文件导入订阅源"""
    opml_path = source.endpoint or str(source.config.get("opml_file", ""))
    if not opml_path:
        raise ValueError("OPML source requires endpoint or opml_file config")

    # 支持相对路径
    if not Path(opml_path).is_absolute():
        opml_path = base_dir / opml_path

    opml_path = Path(opml_path)
    if not opml_path.exists():
        raise ValueError(f"OPML file not found: {opml_path}")

    from core.collector.opml_parser import parse_opML

    content = opml_path.read_text(encoding="utf-8")
    feed_infos = parse_opML(content)

    entries = []
    for idx, feed in enumerate(feed_infos):
        entries.append(RawEntry(
            entry_id=f"opml_{source.source_id}_{idx}",
            feed_id=source.source_id,
            source=source.name,
            url=feed.xml_url,
            title=feed.name,
            content=f"OPML 导入: {feed.name} ({feed.xml_url})",
            published_at=None,
        ))

    logger.info(f"[sources] opml collected {len(entries)} entries from {source.name}")
    return entries


def _collect_jsonl_entries(source: SourceRecord, base_dir: Path) -> list[RawEntry]:
    """从 JSONL 文件批量导入条目"""
    jsonl_path = source.endpoint or str(source.config.get("jsonl_file", ""))
    if not jsonl_path:
        raise ValueError("JSONL source requires endpoint or jsonl_file config")

    # 支持相对路径
    if not Path(jsonl_path).is_absolute():
        jsonl_path = base_dir / jsonl_path

    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        raise ValueError(f"JSONL file not found: {jsonl_path}")

    # 字段映射配置
    url_field = source.config.get("url_field", "url")
    title_field = source.config.get("title_field", "title")
    content_field = source.config.get("content_field", "content")
    id_field = source.config.get("id_field", "id")

    entries = []
    max_results = source.config.get("max_results", 100)

    with jsonl_path.open(encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx >= max_results:
                break
            line = line.strip()
            if not line:
                continue

            item = json.loads(line)

            entry_id = str(item.get(id_field, f"jsonl_{source.source_id}_{idx}"))
            url = str(item.get(url_field, ""))
            title = str(item.get(title_field, url))
            content = str(item.get(content_field, ""))

            entries.append(RawEntry(
                entry_id=entry_id,
                feed_id=source.source_id,
                source=source.name,
                url=url,
                title=title,
                content=content,
                published_at=None,
            ))

    logger.info(f"[sources] jsonl collected {len(entries)} entries from {source.name}")
    return entries
