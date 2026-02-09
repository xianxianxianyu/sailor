from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass(slots=True)
class FeedInfo:
    name: str
    xml_url: str
    html_url: str | None = None


def parse_opml(content: str) -> list[FeedInfo]:
    """解析 OPML 内容，提取 RSS Feed 信息。

    支持 1.md 中的双段 OPML（英文+中文），按 xmlUrl 去重取第一个出现的版本。
    """
    feeds: list[FeedInfo] = []
    seen_urls: set[str] = set()

    # 1.md 包含两段 OPML XML，需要分别解析
    segments = _split_opml_segments(content)

    for segment in segments:
        try:
            root = ElementTree.fromstring(segment)
        except ElementTree.ParseError:
            continue

        for outline in root.iter("outline"):
            xml_url = outline.get("xmlUrl")
            if not xml_url:
                continue

            if xml_url in seen_urls:
                continue
            seen_urls.add(xml_url)

            name = outline.get("text") or outline.get("title") or xml_url
            html_url = outline.get("htmlUrl")
            feeds.append(FeedInfo(name=name, xml_url=xml_url, html_url=html_url))

    return feeds


def _split_opml_segments(content: str) -> list[str]:
    """将可能包含多段 OPML 的内容拆分为独立的 XML 段。"""
    segments: list[str] = []
    marker = "<?xml"
    parts = content.split(marker)

    for i, part in enumerate(parts):
        if i == 0 and not part.strip():
            continue
        if i == 0:
            # 第一段可能没有 <?xml 前缀
            segment = part.strip()
        else:
            segment = marker + part

        segment = segment.strip()
        if segment:
            segments.append(segment)

    return segments
