from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.container import build_container


XML_DECL = '<?xml version="1.0" encoding="UTF-8"?>'
USER_AGENT = "sailor-utest/1.0 (+local rss inspection)"


def split_rss_documents(raw: str) -> list[str]:
    """Split a possibly concatenated RSS file into parseable XML documents."""
    parts = raw.split(XML_DECL)
    docs: list[str] = []
    for part in parts:
        if not part.strip():
            continue
        docs.append(f"{XML_DECL}{part}")
    if docs:
        return docs

    # Fallback: if declaration is missing, treat as a single document.
    return [raw]


def parse_pub_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).isoformat()
    except (TypeError, ValueError):
        return None


def strip_html(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", no_tags).strip()


def fetch_text(url: str, timeout_seconds: int = 20) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        body = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
        text = body.decode(encoding, errors="replace")
        metadata = {
            "status": getattr(response, "status", 200),
            "content_type": response.headers.get("Content-Type", ""),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "bytes": len(body),
        }
        return text, metadata


def extract_items_from_rss(xml_text: str) -> list[dict[str, Any]]:
    ns = {
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    feed_id = (channel.findtext("link") or "rss-feed").strip()
    items: list[dict[str, Any]] = []

    for item in channel.findall("item"):
        title = (item.findtext("title") or "(untitled)").strip()
        url = (item.findtext("link") or "").strip()
        if not url:
            continue

        guid = (item.findtext("guid") or "").strip()
        content_encoded = item.findtext("content:encoded", namespaces=ns)
        description = item.findtext("description")
        content = (content_encoded or description or "").strip()
        published_at = parse_pub_date(item.findtext("pubDate"))

        entry_id = guid or hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        items.append(
            {
                "entry_id": entry_id,
                "feed_id": feed_id,
                "title": title,
                "url": url,
                "published_at": published_at,
                "content": content,
            }
        )
    return items


def dedupe_items_by_url(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        deduped.setdefault(item["url"], item)
    return list(deduped.values())


def build_seed_from_xml_text(
    xml_text: str,
    seed_file: Path,
    max_items: int,
) -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    for doc in split_rss_documents(xml_text):
        try:
            all_items.extend(extract_items_from_rss(doc))
        except ET.ParseError:
            continue

    result = dedupe_items_by_url(all_items)[:max_items]
    seed_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def build_seed_from_file(source_file: Path, seed_file: Path, max_items: int) -> list[dict[str, Any]]:
    raw = source_file.read_text(encoding="utf-8")
    return build_seed_from_xml_text(raw, seed_file, max_items=max_items)


def build_seed_from_feed_url(
    feed_url: str,
    seed_file: Path,
    max_items: int,
    timeout_seconds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    xml_text, fetch_meta = fetch_text(feed_url, timeout_seconds=timeout_seconds)
    items = build_seed_from_xml_text(xml_text, seed_file, max_items=max_items)
    return items, fetch_meta


def run_ingestion_with_seed(project_root: Path, seed_file: Path, db_file: Path) -> dict[str, Any]:
    os.environ["SAILOR_SEED_FILE"] = str(seed_file)
    os.environ["SAILOR_DB_PATH"] = str(db_file)
    os.environ["MINIFLUX_BASE_URL"] = ""
    os.environ["MINIFLUX_TOKEN"] = ""

    container = build_container(project_root)
    # ingestion_service removed — use /sources/{id}/run instead
    result_stub = type("R", (), {"collected_count": 0, "processed_count": 0})()
    result = result_stub
    resources = container.resource_repo.list_resources(status="all")

    return {
        "ingestion_result": asdict(result),
        "resources_count": len(resources),
        "resource_samples": [asdict(resource) for resource in resources[:3]],
    }


def fetch_original_pages(
    items: list[dict[str, Any]],
    limit: int,
    delay_seconds: float,
    timeout_seconds: int,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    target_items = items[:limit]

    for idx, item in enumerate(target_items):
        url = item["url"]
        try:
            html_text, metadata = fetch_text(url, timeout_seconds=timeout_seconds)
            cleaned = strip_html(html_text)
            results.append(
                {
                    "url": url,
                    "status": metadata["status"],
                    "ok": True,
                    "content_type": metadata.get("content_type"),
                    "text_length": len(cleaned),
                    "text_preview": cleaned[:220],
                }
            )
        except HTTPError as exc:
            results.append(
                {
                    "url": url,
                    "status": exc.code,
                    "ok": False,
                    "error": f"HTTPError: {exc.reason}",
                }
            )
        except URLError as exc:
            results.append(
                {
                    "url": url,
                    "status": None,
                    "ok": False,
                    "error": f"URLError: {exc.reason}",
                }
            )

        if idx < len(target_items) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)

    success_count = sum(1 for r in results if r["ok"])
    return {
        "attempted": len(target_items),
        "success_count": success_count,
        "failure_count": len(target_items) - success_count,
        "delay_seconds": delay_seconds,
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect RSS ingestion outputs locally.")
    parser.add_argument("--feed-url", default="", help="RSS URL to fetch once for local testing.")
    parser.add_argument("--source-file", default="1.md", help="Local RSS XML file path.")
    parser.add_argument("--max-items", type=int, default=10, help="Max feed items to convert.")
    parser.add_argument("--fetch-original", action="store_true", help="Try fetching article pages.")
    parser.add_argument(
        "--original-limit",
        type=int,
        default=2,
        help="Max article pages to fetch when --fetch-original is enabled.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=5.0,
        help="Delay between article-page requests.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=20, help="HTTP timeout seconds.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = PROJECT_ROOT
    utest_dir = project_root / "utest"
    utest_dir.mkdir(parents=True, exist_ok=True)

    seed_file = utest_dir / "seed_from_input.json"
    db_file = utest_dir / "sailor_utest.db"
    output_file = utest_dir / "ingestion_output.json"

    if args.feed_url:
        converted, fetch_meta = build_seed_from_feed_url(
            args.feed_url,
            seed_file,
            max_items=args.max_items,
            timeout_seconds=args.timeout_seconds,
        )
        source_meta = {
            "mode": "feed_url",
            "feed_url": args.feed_url,
            "feed_fetch": fetch_meta,
        }
    else:
        source_file = (project_root / args.source_file).resolve()
        if not source_file.exists():
            raise FileNotFoundError(f"RSS source file not found: {source_file}")
        converted = build_seed_from_file(source_file, seed_file, max_items=args.max_items)
        source_meta = {
            "mode": "local_file",
            "input_file": str(source_file),
        }

    report = run_ingestion_with_seed(project_root, seed_file, db_file)
    report["source"] = {
        **source_meta,
        "converted_seed": str(seed_file),
        "converted_items": len(converted),
        "db_file": str(db_file),
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "network_mode": "miniflux_disabled_local_seed_only",
    }

    if args.fetch_original:
        report["original_fetch"] = fetch_original_pages(
            converted,
            limit=max(args.original_limit, 0),
            delay_seconds=max(args.delay_seconds, 0.0),
            timeout_seconds=max(args.timeout_seconds, 1),
        )

    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"\nSaved report: {output_file}")


if __name__ == "__main__":
    main()
