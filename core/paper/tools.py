"""Paper/Research Engine Tool Functions

Tool functions for:
- paper sync HTTP acquisition (arXiv/OpenReview) with tool_calls/raw_captures
- research capture/ingest utilities
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from core.paper.repository import PaperRepository
from core.paper.models import PaperSource
from core.runner.handlers import RunContext

logger = logging.getLogger(__name__)


def paper_fetch_arxiv_atom(
    ctx: RunContext,
    source: PaperSource,
    *,
    timeout_s: int = 30,
) -> tuple[str, str]:
    """Fetch arXiv Atom feed (HTTP acquisition) and save raw capture.

    Returns:
        (capture_id, raw_xml)
    """
    config = json.loads(source.config_json or "{}")
    cursor = json.loads(source.cursor_json) if source.cursor_json else {}

    query = source.endpoint
    start = int(cursor.get("start", 0) or 0)
    max_results = int(config.get("max_results", 100) or 100)
    sort_by = str(config.get("sort_by", "submittedDate") or "submittedDate")
    sort_order = str(config.get("sort_order", "descending") or "descending")

    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query={quote_plus(query)}&"
        f"start={start}&"
        f"max_results={max_results}&"
        f"sortBy={quote_plus(sort_by)}&"
        f"sortOrder={quote_plus(sort_order)}"
    )

    # Idempotency (best-effort): per source + cursor + params
    params_str = f"query={query}:start={start}:max={max_results}:sort_by={sort_by}:sort_order={sort_order}"
    params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:8]
    idempotency_key = f"v1:paper.fetch.arxiv:source={source.source_id}:{params_hash}"

    request = {
        "source_id": source.source_id,
        "platform": "arxiv",
        "query": query,
        "start": start,
        "max_results": max_results,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "url": url,
        "timeout_s": timeout_s,
    }

    def _http_get(_req: dict) -> str:
        req = Request(url, headers={"User-Agent": "Sailor/1.0"})
        with urlopen(req, timeout=timeout_s) as resp:
            return resp.read().decode("utf-8", errors="replace")

    tc, raw_xml = ctx.call_tool_with_trace(
        "paper.fetch_arxiv_atom",
        request=request,
        execute_fn=_http_get,
        idempotency_key=idempotency_key,
    )

    try:
        capture_id = ctx.save_raw_capture(
            content=raw_xml,
            channel="paper_arxiv",
            content_type="xml",
            tool_call_id=tc.tool_call_id,
        )
    except Exception as exc:
        ctx.finish_tool_call(tc.tool_call_id, "failed", error=str(exc)[:500])
        raise

    # Link capture to tool call
    ctx.finish_tool_call(tc.tool_call_id, "succeeded", output_ref=capture_id)
    return capture_id, raw_xml


def paper_fetch_openreview_notes(
    ctx: RunContext,
    source: PaperSource,
    *,
    timeout_s: int = 30,
) -> tuple[str, str]:
    """Fetch OpenReview notes (HTTP acquisition) and save raw capture.

    Returns:
        (capture_id, raw_json_text)
    """
    config = json.loads(source.config_json or "{}")
    cursor = json.loads(source.cursor_json) if source.cursor_json else {}

    endpoint = source.endpoint
    offset = int(cursor.get("offset", 0) or 0)
    limit = int(config.get("limit", 100) or 100)
    details = str(config.get("details", "") or "")
    sort = str(config.get("sort", "tmdate") or "tmdate")

    is_invitation = "/-/" in endpoint
    invitation = endpoint if is_invitation else f"{endpoint}/-/Blind_Submission"

    api_url = (
        "https://api2.openreview.net/notes?"
        f"invitation={quote_plus(invitation)}&"
        f"offset={offset}&"
        f"limit={limit}&"
        f"sort={quote_plus(sort)}"
    )
    if details:
        api_url += f"&details={quote_plus(details)}"

    params_str = f"invitation={invitation}:offset={offset}:limit={limit}:details={details}:sort={sort}"
    params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:8]
    idempotency_key = f"v1:paper.fetch.openreview:source={source.source_id}:{params_hash}"

    request = {
        "source_id": source.source_id,
        "platform": "openreview",
        "endpoint": endpoint,
        "invitation": invitation,
        "offset": offset,
        "limit": limit,
        "details": details,
        "sort": sort,
        "url": api_url,
        "timeout_s": timeout_s,
    }

    def _http_get(_req: dict) -> str:
        req = Request(api_url, headers={"User-Agent": "Sailor/1.0"})
        with urlopen(req, timeout=timeout_s) as resp:
            return resp.read().decode("utf-8", errors="replace")

    tc, raw_json_text = ctx.call_tool_with_trace(
        "paper.fetch_openreview_notes",
        request=request,
        execute_fn=_http_get,
        idempotency_key=idempotency_key,
    )

    try:
        capture_id = ctx.save_raw_capture(
            content=raw_json_text,
            channel="paper_openreview",
            content_type="json",
            tool_call_id=tc.tool_call_id,
        )
    except Exception as exc:
        ctx.finish_tool_call(tc.tool_call_id, "failed", error=str(exc)[:500])
        raise

    ctx.finish_tool_call(tc.tool_call_id, "succeeded", output_ref=capture_id)
    return capture_id, raw_json_text


def research_capture_papers(
    ctx: RunContext,
    paper_repo: PaperRepository,
    program_id: str,
    source_ids: list[str],
    filters: dict,
    window_since: str | None = None,
    window_until: str | None = None,
    limit: int = 1000,
) -> str:
    """Capture papers from database based on filters

    Args:
        ctx: RunContext with job_repo and data_dir
        paper_repo: PaperRepository instance
        program_id: Research program ID for idempotency
        source_ids: List of paper source IDs to query
        filters: Filter dict with categories, keywords, venues
        window_since: Start of time window (ISO datetime string)
        window_until: End of time window (ISO datetime string)
        limit: Maximum number of papers to capture

    Returns:
        capture_id: ID of the saved raw capture
    """
    # Generate idempotency key
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    params_str = f"sources={','.join(sorted(source_ids))}:filters={json.dumps(filters, sort_keys=True)}"
    params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:8]
    idempotency_key = f"v1:research.capture.papers:program={program_id}:date={date_str}:{params_hash}"

    # Record tool call
    tc = ctx.record_tool_call(
        tool_name="research_capture_papers",
        request={
            "program_id": program_id,
            "source_ids": source_ids,
            "filters": filters,
            "window_since": window_since,
            "window_until": window_until,
            "limit": limit,
        },
        idempotency_key=idempotency_key,
    )

    try:
        # Parse time window
        since_dt = datetime.fromisoformat(window_since) if window_since else None
        until_dt = datetime.fromisoformat(window_until) if window_until else None

        # Query papers from repository
        papers = paper_repo.list_papers_by_sources_and_window(
            source_ids=source_ids,
            since=since_dt,
            until=until_dt,
            limit=limit,
            offset=0,
        )

        # Apply additional filters
        filtered_papers = []
        categories = filters.get("categories", [])
        keywords = filters.get("keywords", [])
        venues = filters.get("venues", [])

        for paper in papers:
            # Category filter (check if paper has any of the specified categories)
            # Note: This assumes categories are stored in external_ids_json or raw_meta_json
            # For now, we'll skip category filtering and implement it when needed

            # Keyword filter (check title and abstract)
            if keywords:
                text = f"{paper.title} {paper.abstract or ''}".lower()
                if not any(kw.lower() in text for kw in keywords):
                    continue

            # Venue filter
            if venues and paper.venue:
                if paper.venue not in venues:
                    continue

            filtered_papers.append(paper)

        # Convert papers to serializable format
        papers_data = []
        for paper in filtered_papers:
            papers_data.append({
                "paper_id": paper.paper_id,
                "canonical_id": paper.canonical_id,
                "canonical_url": paper.canonical_url,
                "title": paper.title,
                "abstract": paper.abstract,
                "published_at": paper.published_at.isoformat() if paper.published_at else None,
                "authors_json": paper.authors_json,
                "venue": paper.venue,
                "doi": paper.doi,
                "pdf_url": paper.pdf_url,
            })

        # Save raw capture
        raw_data = {
            "papers": papers_data,
            "program_id": program_id,
            "source_ids": source_ids,
            "filters": filters,
            "window_since": window_since,
            "window_until": window_until,
            "captured_at": datetime.utcnow().isoformat(),
            "total_count": len(papers_data),
        }
        capture_id = ctx.save_raw_capture(
            content=json.dumps(raw_data, ensure_ascii=False, indent=2),
            channel="research",
            tool_call_id=tc.tool_call_id,
        )

        # Finish tool call
        ctx.finish_tool_call(tc.tool_call_id, "succeeded", output_ref=capture_id)

        logger.info(f"[research_capture_papers] Captured {len(papers_data)} papers for program {program_id}")
        return capture_id

    except Exception as exc:
        ctx.finish_tool_call(tc.tool_call_id, "failed", error=str(exc)[:500])
        raise


def research_snapshot_ingest(
    ctx: RunContext,
    paper_repo: PaperRepository,
    program_id: str,
    raw_capture_ref: str,
    window_since: str | None = None,
    window_until: str | None = None,
) -> str:
    """Ingest raw capture into ResearchSnapshot

    Args:
        ctx: RunContext
        paper_repo: PaperRepository instance
        program_id: Research program ID
        raw_capture_ref: capture_id to load
        window_since: Optional window start (ISO datetime)
        window_until: Optional window end (ISO datetime)

    Returns:
        snapshot_id: ID of the created snapshot
    """
    # Load raw capture
    raw_content = ctx.load_raw_capture(raw_capture_ref)
    raw_data = json.loads(raw_content)

    # Extract papers
    papers_data = raw_data.get("papers", [])

    # Extract paper IDs in order
    paper_ids = [p["paper_id"] for p in papers_data]

    # Create snapshot
    captured_at = datetime.fromisoformat(raw_data.get("captured_at", datetime.utcnow().isoformat()))
    snapshot_id = paper_repo.create_research_snapshot(
        program_id=program_id,
        window_since=window_since,
        window_until=window_until,
        captured_at=captured_at,
    )

    # Add snapshot items
    if paper_ids:
        paper_repo.add_research_snapshot_items(snapshot_id, paper_ids)

    logger.info(f"[research_snapshot_ingest] Created snapshot {snapshot_id} with {len(paper_ids)} papers")
    return snapshot_id
