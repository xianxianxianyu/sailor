from __future__ import annotations

import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas import (
    ChannelHealthOut,
    ChannelInfoOut,
    CompareIn,
    CompareSummaryOut,
    ConvertSourceIn,
    CreateSnifferPackIn,
    ImportPackIn,
    ResourceAnalysisOut,
    SaveToKBIn,
    SearchResponseOut,
    SearchSummaryOut,
    SniffQueryIn,
    SniffResultOut,
    SnifferPackFullOut,
    UpdatePackScheduleIn,
)
from core.models import Resource, SniffQuery, SourceRecord

router = APIRouter(prefix="/sniffer", tags=["sniffer"])


def _result_to_out(r) -> SniffResultOut:
    return SniffResultOut(
        result_id=r.result_id,
        channel=r.channel,
        title=r.title,
        url=r.url,
        snippet=r.snippet,
        author=r.author,
        published_at=r.published_at,
        media_type=r.media_type,
        metrics=r.metrics,
        query_keyword=r.query_keyword,
    )

# --- PLACEHOLDER_REST ---


def mount_sniffer_routes(container: AppContainer) -> APIRouter:
    @router.post("/search", response_model=SearchResponseOut)
    def search(payload: SniffQueryIn) -> SearchResponseOut:
        query = SniffQuery(
            keyword=payload.keyword,
            channels=payload.channels,
            time_range=payload.time_range,
            sort_by=payload.sort_by,
            max_results_per_channel=payload.max_results_per_channel,
        )
        results = container.channel_registry.search(query)
        container.sniffer_repo.save_results(results)
        summary = container.summary_engine.summarize(results, payload.keyword)
        return SearchResponseOut(
            results=[_result_to_out(r) for r in results],
            summary=SearchSummaryOut(**summary),
        )

    @router.get("/channels", response_model=list[ChannelInfoOut])
    def list_channels() -> list[ChannelInfoOut]:
        channels = container.channel_registry.list_channels()
        return [ChannelInfoOut(**ch) for ch in channels]

    # --- P1-1: Deep analyze ---

    @router.post("/results/{result_id}/deep-analyze", response_model=ResourceAnalysisOut)
    def deep_analyze(result_id: str):
        sr = container.sniffer_repo.get_result(result_id)
        if not sr:
            raise HTTPException(status_code=404, detail="Result not found")
        resource = Resource(
            resource_id=uuid.uuid4().hex[:12],
            canonical_url=sr.url,
            source=f"sniffer:{sr.channel}",
            provenance={"sniffer_result_id": sr.result_id, "channel": sr.channel},
            title=sr.title,
            published_at=sr.published_at,
            text=sr.snippet or sr.title,
            original_url=sr.url,
            topics=[],
            summary=sr.snippet or "",
        )
        container.resource_repo.upsert(resource)
        analysis = container.article_agent.analyze(resource)
        return ResourceAnalysisOut(
            resource_id=analysis.resource_id,
            summary=analysis.summary,
            topics=json.loads(analysis.topics_json),
            scores=json.loads(analysis.scores_json),
            kb_recommendations=json.loads(analysis.kb_recommendations_json),
            insights=json.loads(analysis.insights_json),
            model=analysis.model,
            prompt_tokens=analysis.prompt_tokens,
            completion_tokens=analysis.completion_tokens,
            status=analysis.status,
            error_message=analysis.error_message,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
        )

    # --- P1-3: Save to KB ---

    @router.post("/results/{result_id}/save-to-kb")
    def save_to_kb(result_id: str, payload: SaveToKBIn):
        sr = container.sniffer_repo.get_result(result_id)
        if not sr:
            raise HTTPException(status_code=404, detail="Result not found")
        kb = container.kb_repo.get_kb(payload.kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        resource = Resource(
            resource_id=uuid.uuid4().hex[:12],
            canonical_url=sr.url,
            source=f"sniffer:{sr.channel}",
            provenance={"sniffer_result_id": sr.result_id, "channel": sr.channel},
            title=sr.title,
            published_at=sr.published_at,
            text=sr.snippet or sr.title,
            original_url=sr.url,
            topics=[],
            summary=sr.snippet or "",
        )
        container.resource_repo.upsert(resource)
        container.kb_repo.add_item(payload.kb_id, resource.resource_id)
        return {"saved": True, "resource_id": resource.resource_id, "kb_id": payload.kb_id}

    # --- P1-3: Convert to source ---

    @router.post("/results/{result_id}/convert-source")
    def convert_source(result_id: str, payload: ConvertSourceIn):
        sr = container.sniffer_repo.get_result(result_id)
        if not sr:
            raise HTTPException(status_code=404, detail="Result not found")
        source = SourceRecord(
            source_id=uuid.uuid4().hex[:12],
            source_type=payload.source_type,
            name=payload.name or sr.title[:60],
            endpoint=sr.url,
            config={"origin": "sniffer", "channel": sr.channel},
            enabled=True,
        )
        container.source_repo.upsert_source(source)
        return {"converted": True, "source_id": source.source_id}

    # --- P1-2: Compare ---

    @router.post("/compare", response_model=CompareSummaryOut)
    def compare(payload: CompareIn):
        results = container.sniffer_repo.get_results_by_ids(payload.result_ids)
        if len(results) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 results to compare")
        summary = container.summary_engine.compare(results, container.llm_client)
        return CompareSummaryOut(
            dimensions=summary.dimensions,
            verdict=summary.verdict,
            model=summary.model,
        )

    # --- P1-4: Import / Export ---

    @router.post("/packs/import", response_model=SnifferPackFullOut)
    def import_pack(payload: ImportPackIn):
        pack = container.pack_manager.import_pack(payload.model_dump())
        return SnifferPackFullOut(**asdict(pack))

    # --- Pack CRUD ---

    @router.get("/packs", response_model=list[SnifferPackFullOut])
    def list_packs():
        packs = container.pack_manager.list_packs()
        return [SnifferPackFullOut(**asdict(p)) for p in packs]

    @router.post("/packs", response_model=SnifferPackFullOut)
    def create_pack(payload: CreateSnifferPackIn):
        query = SniffQuery(
            keyword=payload.query.keyword,
            channels=payload.query.channels,
            time_range=payload.query.time_range,
            sort_by=payload.query.sort_by,
            max_results_per_channel=payload.query.max_results_per_channel,
        )
        pack = container.pack_manager.create_pack(
            name=payload.name, query=query, description=payload.description,
        )
        return SnifferPackFullOut(**asdict(pack))

    @router.delete("/packs/{pack_id}")
    def delete_pack(pack_id: str):
        deleted = container.pack_manager.delete_pack(pack_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Pack not found")
        return {"deleted": True}

    @router.post("/packs/{pack_id}/run", response_model=SearchResponseOut)
    def run_pack(pack_id: str):
        try:
            results = container.pack_manager.run_pack(pack_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        keyword = results[0].query_keyword if results else ""
        summary = container.summary_engine.summarize(results, keyword)
        return SearchResponseOut(
            results=[_result_to_out(r) for r in results],
            summary=SearchSummaryOut(**summary),
        )

    @router.get("/packs/{pack_id}/export")
    def export_pack(pack_id: str):
        data = container.pack_manager.export_pack(pack_id)
        if not data:
            raise HTTPException(status_code=404, detail="Pack not found")
        return data

    # --- P2-1: Schedule ---

    @router.patch("/packs/{pack_id}/schedule", response_model=SnifferPackFullOut)
    def update_schedule(pack_id: str, payload: UpdatePackScheduleIn):
        pack = container.sniffer_repo.update_pack_schedule(pack_id, payload.schedule_cron)
        if not pack:
            raise HTTPException(status_code=404, detail="Pack not found")
        if hasattr(container, "scheduler") and container.scheduler:
            container.scheduler.reschedule(pack)
        return SnifferPackFullOut(**asdict(pack))

    # --- P2-2: Channel health ---

    @router.get("/channels/health", response_model=list[ChannelHealthOut])
    def channel_health():
        adapters = container.channel_registry._adapters
        results = []
        with ThreadPoolExecutor(max_workers=min(len(adapters), 5)) as pool:
            def _check(a):
                t0 = time.time()
                try:
                    status = a.check()
                    latency = int((time.time() - t0) * 1000)
                    return ChannelHealthOut(
                        channel_id=a.channel_id, display_name=a.display_name,
                        icon=a.icon, tier=a.tier,
                        status=status["status"], message=status.get("message", ""),
                        latency_ms=latency,
                    )
                except Exception as exc:
                    latency = int((time.time() - t0) * 1000)
                    return ChannelHealthOut(
                        channel_id=a.channel_id, display_name=a.display_name,
                        icon=a.icon, tier=a.tier,
                        status="off", message=str(exc),
                        latency_ms=latency,
                    )
            futures = {pool.submit(_check, a): a.channel_id for a in adapters.values()}
            for f in as_completed(futures):
                results.append(f.result())
        return results

    return router
