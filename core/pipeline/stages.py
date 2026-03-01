from __future__ import annotations

import hashlib
import re
from html import unescape
from urllib import parse

from core.models import Resource
from core.pipeline.base import PipelineContext, PipelineStage


TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "spm",
    "ref",
}

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "LLM": ("llm", "prompt", "rag", "agent", "embedding"),
    "Infra": ("kubernetes", "cloud", "infra", "platform", "devops"),
    "Database": ("sql", "database", "postgres", "mysql", "index"),
    "Security": ("security", "auth", "vulnerability", "encryption"),
    "Frontend": ("react", "css", "frontend", "typescript", "ui"),
}


class NormalizeStage(PipelineStage):
    def run(self, context: PipelineContext) -> PipelineContext:
        context.canonical_url = canonicalize_url(context.entry.url)
        return context


class FetchExtractStage(PipelineStage):
    def run(self, context: PipelineContext) -> PipelineContext:
        # For the minimal loop, Miniflux entry content is used as extraction source.
        content = context.entry.content or ""
        context.raw_html = content
        context.extracted_text = strip_html(content) if content else context.entry.title
        return context


class CleanStage(PipelineStage):
    def run(self, context: PipelineContext) -> PipelineContext:
        base_text = context.extracted_text or context.entry.title
        normalized = re.sub(r"\s+", " ", base_text).strip()
        context.clean_text = normalized
        return context


class EnrichStage(PipelineStage):
    def run(self, context: PipelineContext) -> PipelineContext:
        text = f"{context.entry.title} {context.clean_text}".lower()
        topics: list[str] = []
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                topics.append(topic)

        context.topics = topics or ["General"]
        context.summary = summarize(context.clean_text)
        return context


class BuildResourceStage(PipelineStage):
    def run(self, context: PipelineContext) -> PipelineContext:
        canonical = context.canonical_url or context.entry.url
        digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
        resource_id = f"res_{digest[:12]}"

        context.resource = Resource(
            resource_id=resource_id,
            canonical_url=canonical,
            source=context.entry.source,
            provenance={
                "source_type": context.entry.source,
                "source_id": context.entry.feed_id,
                "entry_native_id": context.entry.entry_id,
                "adapter_version": "v1",
                "captured_at": context.entry.captured_at.isoformat(),
            },
            title=context.entry.title,
            published_at=context.entry.published_at,
            text=context.clean_text,
            original_url=context.entry.url,
            topics=context.topics or ["General"],
            summary=context.summary,
        )
        return context


def canonicalize_url(url: str) -> str:
    parsed = parse.urlsplit(url)
    query = parse.parse_qsl(parsed.query, keep_blank_values=False)
    filtered = [(key, value) for key, value in query if key.lower() not in TRACKING_QUERY_KEYS]
    clean_query = parse.urlencode(filtered)
    canonical = parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), clean_query, ""))
    return canonical or url


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return unescape(text)


def make_resource_id(canonical_url: str) -> str:
    digest = hashlib.sha1(canonical_url.encode("utf-8")).hexdigest()
    return f"res_{digest[:12]}"


def summarize(text: str, max_len: int = 220) -> str:
    if len(text) <= max_len:
        return text
    trimmed = text[: max_len - 1].rstrip()
    return f"{trimmed}…"
