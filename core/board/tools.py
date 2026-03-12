"""BoardEngine Tool Functions

Tool functions for capturing and ingesting board data.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from core.board.adapters import GitHubTrendingAdapter, HuggingFaceAdapter
from core.board.repository import BoardRepository
from core.runner.handlers import RunContext

logger = logging.getLogger(__name__)


def boards_capture_github(
    ctx: RunContext,
    board_id: str,
    language: str | None = None,
    since: str = "daily",
) -> str:
    """Capture GitHub Trending data

    Args:
        ctx: RunContext with job_repo and data_dir
        board_id: Board ID for idempotency
        language: Programming language filter (optional)
        since: Time range (daily, weekly, monthly)

    Returns:
        capture_id: ID of the saved raw capture
    """
    # Construct URL
    lang_part = f"/{language}" if language else ""
    url = f"https://github.com/trending{lang_part}?since={since}"

    # Generate idempotency key
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    lang_str = language or "all"
    params_str = f"lang={lang_str}:since={since}"
    params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:8]
    idempotency_key = f"v1:boards.capture.github:board={board_id}:date={date_str}:{params_hash}"

    # Record tool call
    tc = ctx.record_tool_call(
        tool_name="boards_capture_github",
        request={"board_id": board_id, "language": language, "since": since, "url": url},
        idempotency_key=idempotency_key,
    )

    try:
        # HTTP GET
        req = Request(url, method="GET")
        req.add_header("User-Agent", "Sailor/1.0")
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        repos = []

        # Find trending repo articles
        for article in soup.select("article.Box-row"):
            try:
                # Extract repo name
                h2 = article.select_one("h2 a")
                if not h2:
                    continue

                full_name = h2.get("href", "").strip("/")
                if "/" not in full_name:
                    continue

                owner, name = full_name.split("/", 1)

                # Extract description
                desc_elem = article.select_one("p.col-9")
                description = desc_elem.get_text(strip=True) if desc_elem else ""

                # Extract stars
                stars = 0
                stars_elem = article.select_one("svg.octicon-star")
                if stars_elem and stars_elem.parent:
                    stars_text = stars_elem.parent.get_text(strip=True).replace(",", "")
                    try:
                        stars = int(stars_text)
                    except ValueError:
                        pass

                # Extract language
                lang_elem = article.select_one("span[itemprop='programmingLanguage']")
                language_name = lang_elem.get_text(strip=True) if lang_elem else ""

                # Extract stars today
                stars_today = 0
                stars_today_elem = article.select_one("span.d-inline-block.float-sm-right")
                if stars_today_elem:
                    stars_today_text = stars_today_elem.get_text(strip=True).split()[0].replace(",", "")
                    try:
                        stars_today = int(stars_today_text)
                    except ValueError:
                        pass

                repos.append({
                    "owner": owner,
                    "name": name,
                    "description": description,
                    "stars": stars,
                    "language": language_name,
                    "stars_today": stars_today,
                    "forks": 0,  # Not available in trending page
                })
            except Exception as exc:
                logger.warning(f"[boards_capture_github] Failed to parse repo: {exc}")
                continue

        # Save raw capture
        raw_data = {"repos": repos, "url": url, "captured_at": datetime.utcnow().isoformat()}
        capture_id = ctx.save_raw_capture(
            content=json.dumps(raw_data, ensure_ascii=False, indent=2),
            channel="github",
            tool_call_id=tc.tool_call_id,
        )

        # Finish tool call
        ctx.finish_tool_call(tc.tool_call_id, "succeeded", output_ref=capture_id)

        return capture_id

    except Exception as exc:
        ctx.finish_tool_call(tc.tool_call_id, "failed", error=str(exc)[:500])
        raise


def boards_capture_huggingface(
    ctx: RunContext,
    board_id: str,
    kind: str = "models",
    limit: int = 100,
) -> str:
    """Capture HuggingFace Trending data

    Args:
        ctx: RunContext with job_repo and data_dir
        board_id: Board ID for idempotency
        kind: Type of content (models, datasets, spaces)
        limit: Maximum number of items to fetch

    Returns:
        capture_id: ID of the saved raw capture
    """
    # Construct URL
    url = f"https://huggingface.co/api/{kind}?sort=trending&limit={limit}"

    # Generate idempotency key
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    params_str = f"kind={kind}:limit={limit}"
    params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:8]
    idempotency_key = f"v1:boards.capture.huggingface:board={board_id}:date={date_str}:{params_hash}"

    # Record tool call
    tc = ctx.record_tool_call(
        tool_name="boards_capture_huggingface",
        request={"board_id": board_id, "kind": kind, "limit": limit, "url": url},
        idempotency_key=idempotency_key,
    )

    try:
        # HTTP GET
        req = Request(url, method="GET")
        req.add_header("User-Agent", "Sailor/1.0")
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Save raw capture
        raw_data = {"items": data, "kind": kind, "url": url, "captured_at": datetime.utcnow().isoformat()}
        capture_id = ctx.save_raw_capture(
            content=json.dumps(raw_data, ensure_ascii=False, indent=2),
            channel="huggingface",
            tool_call_id=tc.tool_call_id,
        )

        # Finish tool call
        ctx.finish_tool_call(tc.tool_call_id, "succeeded", output_ref=capture_id)

        return capture_id

    except Exception as exc:
        ctx.finish_tool_call(tc.tool_call_id, "failed", error=str(exc)[:500])
        raise


def boards_snapshot_ingest(
    ctx: RunContext,
    board_repo: BoardRepository,
    board_id: str,
    raw_capture_ref: str,
    window_since: str | None = None,
    window_until: str | None = None,
    adapter_version: str = "v1",
) -> str:
    """Ingest raw capture into BoardSnapshot

    Args:
        ctx: RunContext
        board_repo: BoardRepository instance
        board_id: Board ID
        raw_capture_ref: capture_id to load
        window_since: Optional window start (ISO datetime)
        window_until: Optional window end (ISO datetime)
        adapter_version: Adapter version string

    Returns:
        snapshot_id: ID of the created snapshot
    """
    # Load raw capture
    raw_content = ctx.load_raw_capture(raw_capture_ref)
    raw_data = json.loads(raw_content)

    # Get board to determine provider
    board = board_repo.get_board(board_id)
    if not board:
        raise ValueError(f"Board not found: {board_id}")

    # Select adapter based on provider
    if board.provider == "github":
        adapter = GitHubTrendingAdapter()
    elif board.provider == "huggingface":
        adapter = HuggingFaceAdapter(kind=board.kind)
    else:
        raise ValueError(f"Unsupported provider: {board.provider}")

    # Parse raw data
    items = adapter.parse(raw_data)

    # Convert meta dict to meta_json string
    for item in items:
        if "meta" in item:
            item["meta_json"] = json.dumps(item.pop("meta"), ensure_ascii=False)

    # Create snapshot
    captured_at = datetime.fromisoformat(raw_data.get("captured_at", datetime.utcnow().isoformat()))
    snapshot_id = board_repo.create_snapshot(
        board_id=board_id,
        window_since=window_since,
        window_until=window_until,
        captured_at=captured_at,
        raw_capture_ref=raw_capture_ref,
        adapter_version=adapter_version,
    )

    # Add snapshot items
    board_repo.add_snapshot_items(snapshot_id, items)

    return snapshot_id
