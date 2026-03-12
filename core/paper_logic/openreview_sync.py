"""OpenReview normalization (logic layer)

逻辑层：只做纯解析/归一化（不包含任何网络 I/O）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from core.paper.models import PaperRecord, PaperSource, PaperSyncResult

logger = logging.getLogger(__name__)


def normalize_openreview_notes(source: PaperSource, raw_json_text: str) -> PaperSyncResult:
    """
    归一化 OpenReview notes 响应（raw JSON -> PaperSyncResult）

    source.endpoint 格式示例:
    - "ICLR.cc/2024/Conference" - venue ID
    - "NeurIPS.cc/2023/Conference/-/Blind_Submission" - invitation ID

    source.config_json 支持的参数:
    - limit: int (默认 100)
    - details: str (comma-separated, e.g., "replies,invitation")
    - sort: str (cdate/tmdate/number, 默认 tmdate)

    source.cursor_json 格式:
    - offset: int (分页偏移)
    - last_modified: str (上次修改时间)
    """
    config = json.loads(source.config_json)
    cursor = json.loads(source.cursor_json) if source.cursor_json else {}

    # 解析配置
    endpoint = source.endpoint
    offset = cursor.get("offset", 0)
    limit = config.get("limit", 100)
    details = config.get("details", "")
    sort = config.get("sort", "tmdate")

    logger.info(
        "[openreview] 开始解析: endpoint=%s, offset=%d, limit=%d",
        endpoint,
        offset,
        limit,
    )
    data = json.loads(raw_json_text or "{}")

    # 解析响应
    notes = data.get("notes", [])
    papers: list[PaperRecord] = []

    for note in notes:
        try:
            # forum ID 作为唯一标识
            forum_id = note.get("forum") or note.get("id")
            if not forum_id:
                continue

            # 内容字段
            content = note.get("content", {})

            # 标题
            title = content.get("title")
            if isinstance(title, dict):
                title = title.get("value", "Untitled")
            elif not title:
                title = "Untitled"

            # 摘要
            abstract = content.get("abstract")
            if isinstance(abstract, dict):
                abstract = abstract.get("value")

            # 作者
            authors = content.get("authors")
            if isinstance(authors, dict):
                authors = authors.get("value", [])
            if not isinstance(authors, list):
                authors = None

            # 发布时间（使用 cdate - creation date）
            cdate = note.get("cdate")
            published_at = None
            if cdate:
                try:
                    # OpenReview cdate 是 Unix timestamp (milliseconds)
                    published_at = datetime.fromtimestamp(cdate / 1000.0)
                except (ValueError, TypeError):
                    pass

            # Venue（从 invitation 提取）
            invitation = note.get("invitation", "")
            venue = None
            if "/" in invitation:
                # e.g., "ICLR.cc/2024/Conference/-/Blind_Submission" -> "ICLR.cc/2024/Conference"
                venue = invitation.split("/-/")[0]

            # PDF URL（如果有）
            pdf_url = None
            pdf_field = content.get("pdf")
            if pdf_field:
                if isinstance(pdf_field, dict):
                    pdf_url = pdf_field.get("value")
                elif isinstance(pdf_field, str):
                    pdf_url = pdf_field
                # 补全为完整 URL
                if pdf_url and not pdf_url.startswith("http"):
                    pdf_url = f"https://openreview.net{pdf_url}"

            # Canonical URL
            canonical_url = f"https://openreview.net/forum?id={forum_id}"

            # 构造 PaperRecord
            papers.append(
                PaperRecord(
                    canonical_id=f"openreview:{forum_id}",
                    canonical_url=canonical_url,
                    title=title,
                    item_key=f"v1:openreview:{forum_id}",
                    abstract=abstract,
                    published_at=published_at,
                    authors=authors,
                    venue=venue,
                    doi=None,  # OpenReview 通常没有 DOI
                    pdf_url=pdf_url,
                    external_ids={"openreview_forum_id": forum_id},
                    raw_meta=note,
                )
            )

        except Exception as e:
            logger.warning("[openreview] 解析 note 失败: %s", e)
            continue

    # 更新游标
    next_cursor = {"offset": offset + len(papers)}
    if papers:
        # 记录最新的 modified time
        latest_modified = max(
            (note.get("tmdate", 0) for note in notes),
            default=0,
        )
        if latest_modified:
            next_cursor["last_modified"] = datetime.fromtimestamp(latest_modified / 1000.0).isoformat()

    metrics = {
        "fetched": len(papers),
        "api_calls": 1,
        "endpoint": endpoint,
        "offset": offset,
        "limit": limit,
    }

    logger.info("[openreview] 同步完成: fetched=%d", len(papers))

    return PaperSyncResult(
        papers=papers,
        next_cursor_json=next_cursor,
        metrics_json=metrics,
    )

