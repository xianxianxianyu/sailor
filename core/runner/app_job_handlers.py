"""AppJobHandlers — jobified heavy endpoints (P0-3).

These handlers are executed by JobRunner (typically in the worker process).
Routers should only enqueue + optionally wait, never run heavy work inline.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from core.agent.article_agent import ArticleAnalysisAgent
from core.agent.kb_agent import KBClusterAgent
from core.models import Job, Resource, SourceRecord
from core.pipeline.stages import canonicalize_url, make_resource_id
from core.sniffer.summary_engine import SummaryEngine
from core.storage.analysis_repository import AnalysisRepository
from core.storage.repositories import KnowledgeBaseRepository, ResourceRepository
from core.storage.sniffer_repository import SnifferRepository
from core.storage.source_repository import SourceRepository

from .handlers import RunContext

logger = logging.getLogger(__name__)


class ResourceAnalyzeHandler:
    """Analyze a single resource via LLM and persist analysis artifact."""

    def __init__(
        self,
        resource_repo: ResourceRepository,
        analysis_repo: AnalysisRepository,
        article_agent: ArticleAnalysisAgent,
    ) -> None:
        self.resource_repo = resource_repo
        self.analysis_repo = analysis_repo
        self.article_agent = article_agent

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        resource_id = input_data["resource_id"]

        ctx.emit_event("ResourceAnalyzeStarted", {"resource_id": resource_id})

        existing = self.analysis_repo.get_by_resource_id(resource_id)
        if existing and existing.status == "completed":
            ctx.emit_event("ResourceAnalyzeSkipped", {"resource_id": resource_id})
            return json.dumps({"resource_id": resource_id, "skipped": True, "status": "completed"})

        resource = self.resource_repo.get_resource(resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")

        text = resource.text or ""
        if len(text) < 20:
            raise ValueError("Content too short for analysis")

        analysis = ctx.call_tool(
            "article_agent:analyze",
            {"resource_id": resource_id, "title": resource.title},
            lambda _req: self.article_agent.analyze(resource),
        )

        ctx.emit_event("ResourceAnalyzeFinished", {
            "resource_id": resource_id,
            "analysis_status": analysis.status,
        })

        if analysis.status != "completed":
            raise RuntimeError(analysis.error_message or "LLM analysis failed")

        return json.dumps({"resource_id": resource_id, "status": analysis.status})


class AnalysisRunHandler:
    """Batch analyze resources via LLM (persisting analysis artifacts)."""

    def __init__(self, article_agent: ArticleAnalysisAgent) -> None:
        self.article_agent = article_agent

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        resource_ids: list[str] | None = input_data.get("resource_ids")

        ctx.emit_event("AnalysisRunStarted", {"resource_ids": resource_ids})

        analyzed, failed = ctx.call_tool(
            "article_agent:analyze_pending",
            {"resource_ids": resource_ids},
            lambda _req: self.article_agent.analyze_pending(resource_ids),
        )

        ctx.emit_event("AnalysisRunFinished", {"analyzed": analyzed, "failed": failed})

        # Partial success: mark job error_class="partial" for observability
        if failed and analyzed:
            job.metadata["_error_class"] = "partial"
        if failed and not analyzed:
            raise RuntimeError("All analyses failed")

        return json.dumps({"analyzed_count": analyzed, "failed_count": failed})


class KBReportsGenerateHandler:
    """Generate KB reports (cluster/association/summary) via LLM."""

    def __init__(self, kb_agent: KBClusterAgent) -> None:
        self.kb_agent = kb_agent

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        kb_id = input_data["kb_id"]
        report_types: list[str] | None = input_data.get("report_types")

        ctx.emit_event("KBReportsGenerateStarted", {"kb_id": kb_id, "report_types": report_types})

        reports = ctx.call_tool(
            "kb_agent:generate_all",
            {"kb_id": kb_id, "report_types": report_types},
            lambda _req: self.kb_agent.generate_all(kb_id, report_types),
        )

        failed = [r for r in reports if getattr(r, "status", "") == "failed"]
        if failed and len(failed) != len(reports):
            job.metadata["_error_class"] = "partial"
        if failed and len(failed) == len(reports):
            # surface an error message for /jobs
            msg = failed[0].error_message if getattr(failed[0], "error_message", None) else "KB report generation failed"
            raise RuntimeError(msg)

        ctx.emit_event("KBReportsGenerateFinished", {
            "kb_id": kb_id,
            "report_count": len(reports),
            "failed_count": len(failed),
        })

        return json.dumps({
            "kb_id": kb_id,
            "report_ids": [r.report_id for r in reports],
        })


class SnifferDeepAnalyzeHandler:
    """Deep analyze a sniffer result by converting it into a Resource and running LLM analysis."""

    def __init__(
        self,
        sniffer_repo: SnifferRepository,
        resource_repo: ResourceRepository,
        article_agent: ArticleAnalysisAgent,
    ) -> None:
        self.sniffer_repo = sniffer_repo
        self.resource_repo = resource_repo
        self.article_agent = article_agent

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        result_id = input_data["result_id"]

        sr = self.sniffer_repo.get_result(result_id)
        if not sr:
            raise ValueError("Result not found")

        ctx.emit_event("SnifferDeepAnalyzeStarted", entity_refs={"result_id": result_id})

        canonical = canonicalize_url(sr.url)
        resource = Resource(
            resource_id=make_resource_id(canonical),
            canonical_url=canonical,
            source=f"sniffer:{sr.channel}",
            provenance={"sniffer_result_id": sr.result_id, "channel": sr.channel},
            title=sr.title,
            published_at=sr.published_at,
            text=sr.snippet or sr.title,
            original_url=sr.url,
            topics=[],
            summary=sr.snippet or "",
        )
        self.resource_repo.upsert(resource)

        analysis = ctx.call_tool(
            "article_agent:analyze",
            {"resource_id": resource.resource_id, "sniffer_result_id": result_id},
            lambda _req: self.article_agent.analyze(resource),
        )

        ctx.emit_event(
            "SnifferDeepAnalyzeFinished",
            entity_refs={"result_id": result_id, "resource_id": analysis.resource_id},
            payload={"analysis_status": analysis.status},
        )

        if analysis.status != "completed":
            raise RuntimeError(analysis.error_message or "Deep analyze failed")

        return json.dumps({"resource_id": analysis.resource_id})


class SnifferSaveToKBHandler:
    """Save a sniffer result into a knowledge base (jobified for traceability)."""

    def __init__(
        self,
        sniffer_repo: SnifferRepository,
        resource_repo: ResourceRepository,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self.sniffer_repo = sniffer_repo
        self.resource_repo = resource_repo
        self.kb_repo = kb_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        result_id: str = input_data["result_id"]
        kb_id: str = input_data["kb_id"]

        sr = self.sniffer_repo.get_result(result_id)
        if not sr:
            raise ValueError("Result not found")
        if not self.kb_repo.get_kb(kb_id):
            raise ValueError("Knowledge base not found")

        ctx.emit_event("SnifferSaveToKBStarted", entity_refs={"result_id": result_id, "kb_id": kb_id}, actor="user")

        canonical = canonicalize_url(sr.url)
        resource = Resource(
            resource_id=make_resource_id(canonical),
            canonical_url=canonical,
            source=f"sniffer:{sr.channel}",
            provenance={"sniffer_result_id": sr.result_id, "channel": sr.channel},
            title=sr.title,
            published_at=sr.published_at,
            text=sr.snippet or sr.title,
            original_url=sr.url,
            topics=[],
            summary=sr.snippet or "",
        )
        self.resource_repo.upsert(resource)
        self.kb_repo.add_item(kb_id, resource.resource_id)

        ctx.emit_event(
            "SavedToKB",
            actor="user",
            entity_refs={"result_id": result_id, "resource_id": resource.resource_id, "kb_id": kb_id},
        )

        return json.dumps({"saved": True, "resource_id": resource.resource_id, "kb_id": kb_id})


class SnifferConvertSourceHandler:
    """Convert a sniffer result into a Source (jobified for traceability)."""

    def __init__(self, sniffer_repo: SnifferRepository, source_repo: SourceRepository) -> None:
        self.sniffer_repo = sniffer_repo
        self.source_repo = source_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        result_id: str = input_data["result_id"]
        source_type: str = str(input_data.get("source_type") or "rss")
        name: str | None = input_data.get("name")

        sr = self.sniffer_repo.get_result(result_id)
        if not sr:
            raise ValueError("Result not found")

        source = SourceRecord(
            source_id=uuid.uuid4().hex[:12],
            source_type=source_type,
            name=name or sr.title[:60],
            endpoint=sr.url,
            config={"origin": "sniffer", "channel": sr.channel},
            enabled=True,
        )
        self.source_repo.upsert_source(source)

        ctx.emit_event(
            "ConvertedToSource",
            actor="user",
            entity_refs={"result_id": result_id, "source_id": source.source_id},
        )

        return json.dumps({"converted": True, "source_id": source.source_id})


class SnifferCompareHandler:
    """LLM-powered compare of multiple sniffer results."""

    def __init__(self, sniffer_repo: SnifferRepository, summary_engine: SummaryEngine, llm_client) -> None:
        self.sniffer_repo = sniffer_repo
        self.summary_engine = summary_engine
        self.llm_client = llm_client

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        result_ids: list[str] = input_data["result_ids"]
        if len(result_ids) < 2:
            raise ValueError("Need at least 2 results to compare")

        ctx.emit_event("SnifferCompareStarted", {"result_count": len(result_ids)})

        results = self.sniffer_repo.get_results_by_ids(result_ids)
        summary = ctx.call_tool(
            "sniffer:compare",
            {"result_ids": result_ids},
            lambda _req: self.summary_engine.compare(results, self.llm_client),
        )

        ctx.emit_event("SnifferCompareFinished", {"model": summary.model})

        return json.dumps({
            "dimensions": summary.dimensions,
            "verdict": summary.verdict,
            "model": summary.model,
        })



def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _make_source_id(source_type: str, endpoint: str | None, name: str) -> str:
    if source_type in ("rss", "atom", "jsonfeed") and endpoint:
        return "feed_" + hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:12]
    key = f"{source_type}:{endpoint or ''}:{name}".encode("utf-8")
    return "src_" + hashlib.sha256(key).hexdigest()[:12]


def _build_source_record_from_payload(payload: dict[str, Any]) -> SourceRecord:
    source_type = str(payload.get("source_type") or "rss")
    endpoint_raw = payload.get("endpoint") or payload.get("xml_url") or payload.get("url")
    endpoint = str(endpoint_raw) if endpoint_raw else None
    name = str(payload.get("name") or endpoint or "Unnamed Source")
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    for key in ("html_url", "headers", "method", "items_path", "url_field", "title_field", "tags"):
        if key in payload and key not in config:
            config[key] = payload[key]
    schedule_minutes = max(_coerce_int(payload.get("schedule_minutes", payload.get("poll_minutes", 30)), 30), 1)
    source_id = str(payload.get("source_id") or _make_source_id(source_type, endpoint, name))
    return SourceRecord(
        source_id=source_id,
        source_type=source_type,
        name=name,
        endpoint=endpoint,
        config=config,
        enabled=bool(payload.get("enabled", True)),
        schedule_minutes=schedule_minutes,
    )


class SourceCatalogUpsertHandler:
    """Execute a confirmed source upsert."""

    def __init__(self, source_repo: SourceRepository) -> None:
        self.source_repo = source_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        source = _build_source_record_from_payload(input_data)
        self.source_repo.upsert_source(source)
        ctx.emit_event("SourceUpserted", entity_refs={"source_id": source.source_id})
        return json.dumps({"source_id": source.source_id, "status": "upserted"})


class SourceImportFeedsHandler:
    """Execute a confirmed bulk feed import."""

    def __init__(self, source_repo: SourceRepository) -> None:
        self.source_repo = source_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        items = input_data.get("sources") or input_data.get("feeds") or input_data.get("items")
        if not isinstance(items, list):
            if any(key in input_data for key in ("source_id", "source_type", "endpoint", "xml_url", "url", "name")):
                items = [input_data]
            else:
                raise ValueError("No feeds provided for import")

        source_ids: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            source = _build_source_record_from_payload(item)
            self.source_repo.upsert_source(source)
            source_ids.append(source.source_id)

        ctx.emit_event("FeedsImported", payload={"imported_count": len(source_ids)})
        return json.dumps({"imported_count": len(source_ids), "source_ids": source_ids})


class SourceDeleteHandler:
    """Execute a confirmed source delete."""

    def __init__(self, source_repo: SourceRepository) -> None:
        self.source_repo = source_repo

    def execute(self, job: Job, ctx: RunContext) -> str | None:
        input_data = json.loads(job.input_json or "{}")
        source_id = str(input_data.get("source_id") or "")
        if not source_id:
            raise ValueError("source_id is required")
        deleted = self.source_repo.delete_source(source_id)
        if not deleted:
            raise ValueError("Source not found")
        ctx.emit_event("SourceDeleted", entity_refs={"source_id": source_id})
        return json.dumps({"source_id": source_id, "deleted": True})
