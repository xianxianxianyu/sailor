"""Source entry collectors — extracted from backend/app/routers/sources.py."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import feedparser

from core.models import RawEntry, SourceRecord

logger = logging.getLogger(__name__)


def collect_source_entries(source: SourceRecord, base_dir: Path) -> list[RawEntry]:
    """Dispatch to the appropriate collector based on source_type."""
    if source.source_type == "rss":
        return _collect_rss_entries(source)
    if source.source_type == "atom":
        return _collect_atom_entries(source)
    if source.source_type == "jsonfeed":
        return _collect_jsonfeed_entries(source)
    if source.source_type == "web_page":
        return _collect_web_entries(source)
    if source.source_type == "manual_file":
        return _collect_manual_entries(source, base_dir)
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
        return _collect_opml_entries(source, base_dir)
    if source.source_type == "jsonl":
        return _collect_jsonl_entries(source, base_dir)

    raise ValueError(f"Unsupported source_type: {source.source_type}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# RSS
# ---------------------------------------------------------------------------

def _collect_rss_entries(source: SourceRecord) -> list[RawEntry]:
    xml_url = source.endpoint or str(source.config.get("xml_url") or "")
    if not xml_url:
        raise ValueError("RSS source requires xml_url or endpoint")

    parsed = feedparser.parse(xml_url)

    # Only raise error if parsing completely failed (no entries at all)
    if not parsed.entries:
        if getattr(parsed, "bozo", False):
            bozo_exception = getattr(parsed, 'bozo_exception', 'unknown')
            logger.warning(f"RSS parse warning for {xml_url}: {bozo_exception}")
            # If there are truly no entries, raise error
            raise ValueError(f"RSS parse failed: {bozo_exception}")
        # No entries but no error - just return empty list
        logger.info(f"RSS feed {xml_url} has no entries")
        return []

    # Log warning if bozo but we have entries (minor XML issues)
    if getattr(parsed, "bozo", False):
        logger.warning(f"RSS feed {xml_url} has minor XML issues but parsed successfully")

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


# ---------------------------------------------------------------------------
# Web page
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Manual file
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Academic API
# ---------------------------------------------------------------------------

def _collect_academic_entries(source: SourceRecord) -> list[RawEntry]:
    """采集学术 API 源（arXiv 等）"""
    config = source.config
    platform = config.get("platform", "arxiv")

    if platform == "arxiv":
        from core.collector.arxiv_engine import ArxivCollector
        collector = ArxivCollector(config)
        return collector.collect()

    raise ValueError(f"Unsupported academic platform: {platform}")


# ---------------------------------------------------------------------------
# API (juejin etc.)
# ---------------------------------------------------------------------------

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
        "sort_type": 300,
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


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------

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
        namespaces = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                     'xhtml': 'http://www.w3.org/1999/xhtml'}

        for url_elem in root.findall('.//sm:url', namespaces) or root.findall('.//url'):
            loc = url_elem.find('sm:loc', namespaces) or url_elem.find('loc')
            if loc is None or not loc.text:
                continue

            url = loc.text
            entry_id = "sitemap_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

            title = url.split('/')[-1] or url
            link_elem = url_elem.find('xhtml:link', namespaces)
            if link_elem is not None and link_elem.get('title'):
                title = link_elem.get('title')

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


# ---------------------------------------------------------------------------
# API JSON
# ---------------------------------------------------------------------------

def _collect_api_json_entries(source: SourceRecord) -> list[RawEntry]:
    """采集 API JSON 源"""
    api_url = source.endpoint
    if not api_url:
        raise ValueError("api_json source requires endpoint (URL)")

    user_agent = str(source.config.get("user_agent") or "SailorSourceCollector/1.0")
    headers = {"User-Agent": user_agent}

    custom_headers = source.config.get("headers", {})
    if isinstance(custom_headers, dict):
        headers.update(custom_headers)

    method = source.config.get("method", "GET").upper()
    timeout = int(source.config.get("timeout", 20))

    request_kwargs: dict[str, Any] = {"headers": headers}

    if method == "POST":
        request_kwargs["data"] = source.config.get("body", "").encode("utf-8")
        request_kwargs["headers"]["Content-Type"] = source.config.get("content_type", "application/json")

    request = Request(api_url, **request_kwargs)
    with urlopen(request, timeout=timeout) as response:
        json_data = json.loads(response.read().decode("utf-8", errors="ignore"))

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

        url_field = source.config.get("url_field", "url")
        title_field = source.config.get("title_field", "title")
        content_field = source.config.get("content_field", "content")
        id_field = source.config.get("id_field", "id")

        entry_id = str(item.get(id_field, f"api_json_{source.source_id}_{idx}"))
        url = str(item.get(url_field, ""))
        title = str(item.get(title_field, url))
        content = str(item.get(content_field, ""))

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


# ---------------------------------------------------------------------------
# Atom
# ---------------------------------------------------------------------------

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
        published_raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
        published_at = _parse_datetime(str(published_raw)) if published_raw else None

        entries.append(RawEntry(
            entry_id=link or f"{source.name}:{title}",
            feed_id=source.source_id,
            source=source.name,
            url=link,
            title=title,
            content=summary,
            published_at=published_at,
        ))

    logger.info(f"[sources] atom collected {len(entries)} entries from {source.name}")
    return entries


# ---------------------------------------------------------------------------
# JSON Feed
# ---------------------------------------------------------------------------

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

    if "title" in data and "items" in data:
        items = data.get("items", [])

    entries = []
    for idx, item in enumerate(items[:source.config.get("max_results", 50)]):
        if not isinstance(item, dict):
            continue

        url = str(item.get("url") or item.get("external_url") or "")
        title = str(item.get("title") or url)
        content = str(item.get("content_html") or item.get("content_text") or item.get("summary") or "")
        entry_id = str(item.get("id") or f"jsonfeed_{source.source_id}_{idx}")
        published_at = _parse_datetime(item.get("date_published") or item.get("date_modified"))

        entries.append(RawEntry(
            entry_id=entry_id,
            feed_id=source.source_id,
            source=source.name,
            url=url,
            title=title,
            content=content,
            published_at=published_at,
        ))

    logger.info(f"[sources] jsonfeed collected {len(entries)} entries from {source.name}")
    return entries


# ---------------------------------------------------------------------------
# API XML
# ---------------------------------------------------------------------------

def _collect_api_xml_entries(source: SourceRecord) -> list[RawEntry]:
    """采集 API XML 源"""
    import xml.etree.ElementTree as ET

    api_url = source.endpoint
    if not api_url:
        raise ValueError("api_xml source requires endpoint (URL)")

    user_agent = str(source.config.get("user_agent") or "SailorSourceCollector/1.0")
    request = Request(api_url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=20) as response:
        xml_content = response.read().decode("utf-8", errors="ignore")

    root = ET.fromstring(xml_content)

    items_path = source.config.get("items_path", "")
    if items_path:
        items = root.findall(items_path)
    else:
        items = list(root)

    url_field = source.config.get("url_field", "url")
    title_field = source.config.get("title_field", "title")
    content_field = source.config.get("content_field", "content")
    id_field = source.config.get("id_field", "id")

    entries = []
    max_results = source.config.get("max_results", 20)

    for idx, item in enumerate(items[:max_results]):
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


# ---------------------------------------------------------------------------
# OPML
# ---------------------------------------------------------------------------

def _collect_opml_entries(source: SourceRecord, base_dir: Path) -> list[RawEntry]:
    """从 OPML 文件导入订阅源"""
    opml_path = source.endpoint or str(source.config.get("opml_file", ""))
    if not opml_path:
        raise ValueError("OPML source requires endpoint or opml_file config")

    if not Path(opml_path).is_absolute():
        opml_path = base_dir / opml_path

    opml_path = Path(opml_path)
    if not opml_path.exists():
        raise ValueError(f"OPML file not found: {opml_path}")

    from core.collector.opml_parser import parse_opml

    content = opml_path.read_text(encoding="utf-8")
    feed_infos = parse_opml(content)

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


# ---------------------------------------------------------------------------
# JSONL
# ---------------------------------------------------------------------------

def _collect_jsonl_entries(source: SourceRecord, base_dir: Path) -> list[RawEntry]:
    """从 JSONL 文件批量导入条目"""
    jsonl_path = source.endpoint or str(source.config.get("jsonl_file", ""))
    if not jsonl_path:
        raise ValueError("JSONL source requires endpoint or jsonl_file config")

    if not Path(jsonl_path).is_absolute():
        jsonl_path = base_dir / jsonl_path

    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        raise ValueError(f"JSONL file not found: {jsonl_path}")

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
