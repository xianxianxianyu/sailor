"""arXiv normalization (logic layer)

逻辑层：只做纯解析/归一化（不包含任何网络 I/O）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from xml.etree import ElementTree as ET

from core.paper.models import PaperRecord, PaperSource, PaperSyncResult

logger = logging.getLogger(__name__)


def normalize_arxiv_atom(source: PaperSource, raw_xml: str) -> PaperSyncResult:
    """
    归一化 arXiv Atom feed（raw XML -> PaperSyncResult）

    source.endpoint 格式示例:
    - "cat:cs.AI" - 按类别查询
    - "au:Hinton" - 按作者查询
    - "ti:transformer" - 按标题查询

    source.config_json 支持的参数:
    - max_results: int (默认 100)
    - sort_by: str (submittedDate/lastUpdatedDate/relevance, 默认 submittedDate)
    - sort_order: str (ascending/descending, 默认 descending)

    source.cursor_json 格式:
    - start: int (分页起始位置)
    - last_updated: str (上次更新时间，用于增量)
    """
    config = json.loads(source.config_json)
    cursor = json.loads(source.cursor_json) if source.cursor_json else {}

    # 解析配置
    query = source.endpoint
    start = cursor.get("start", 0)
    max_results = config.get("max_results", 100)
    sort_by = config.get("sort_by", "submittedDate")
    sort_order = config.get("sort_order", "descending")

    logger.info(
        "[arxiv] 开始解析: query=%s, start=%d, max_results=%d",
        query,
        start,
        max_results,
    )

    # 解析 XML
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as e:
        logger.exception("[arxiv] XML 解析失败")
        raise RuntimeError(f"arXiv XML parse failed: {e}")

    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    papers: list[PaperRecord] = []
    for entry in root.findall("atom:entry", ns):
        try:
            # 提取 arXiv ID
            id_elem = entry.find("atom:id", ns)
            if id_elem is None or not id_elem.text:
                continue
            arxiv_id = id_elem.text.split("/")[-1]  # http://arxiv.org/abs/2401.12345 -> 2401.12345

            # 标题
            title_elem = entry.find("atom:title", ns)
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled"

            # 摘要
            summary_elem = entry.find("atom:summary", ns)
            abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else None

            # 发布时间
            published_elem = entry.find("atom:published", ns)
            published_at = None
            if published_elem is not None and published_elem.text:
                try:
                    published_at = datetime.fromisoformat(published_elem.text.replace("Z", "+00:00"))
                except ValueError:
                    pass

            # 作者
            authors = []
            for author_elem in entry.findall("atom:author", ns):
                name_elem = author_elem.find("atom:name", ns)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())

            # PDF 链接
            pdf_url = None
            for link_elem in entry.findall("atom:link", ns):
                if link_elem.attrib.get("title") == "pdf":
                    pdf_url = link_elem.attrib.get("href")
                    break

            # DOI（如果有）
            doi_elem = entry.find("arxiv:doi", ns)
            doi = doi_elem.text.strip() if doi_elem is not None and doi_elem.text else None

            # 主分类
            primary_category_elem = entry.find("arxiv:primary_category", ns)
            venue = None
            if primary_category_elem is not None:
                venue = primary_category_elem.attrib.get("term")  # e.g., cs.AI

            # 构造 PaperRecord
            papers.append(
                PaperRecord(
                    canonical_id=f"arxiv:{arxiv_id}",
                    canonical_url=f"https://arxiv.org/abs/{arxiv_id}",
                    title=title,
                    item_key=f"v1:arxiv:{arxiv_id}",
                    abstract=abstract,
                    published_at=published_at,
                    authors=authors if authors else None,
                    venue=venue,
                    doi=doi,
                    pdf_url=pdf_url,
                    external_ids={"arxiv_id": arxiv_id},
                    raw_meta={"entry_xml": ET.tostring(entry, encoding="unicode")},
                )
            )

        except Exception as e:
            logger.warning("[arxiv] 解析 entry 失败: %s", e)
            continue

    # 更新游标
    next_cursor = {"start": start + len(papers)}
    if papers:
        # 记录最新的 published_at 用于增量同步
        latest_published = max(
            (p.published_at for p in papers if p.published_at),
            default=None,
        )
        if latest_published:
            next_cursor["last_updated"] = latest_published.isoformat()

    metrics = {
        "fetched": len(papers),
        "api_calls": 1,
        "query": query,
        "start": start,
        "max_results": max_results,
    }

    logger.info("[arxiv] 同步完成: fetched=%d", len(papers))

    return PaperSyncResult(
        papers=papers,
        next_cursor_json=next_cursor,
        metrics_json=metrics,
    )
