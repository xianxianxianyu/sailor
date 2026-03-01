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
    ProvenanceEventOut,
    ResourceAnalysisOut,
    SaveToKBIn,
    SearchResponseOut,
    SearchSummaryOut,
    SniffQueryIn,
    SniffResultOut,
    SnifferPackFullOut,
    SnifferRunOut,
    UpdatePackScheduleIn,
)
from core.models import Job, ProvenanceEvent, Resource, SniffQuery, SourceRecord

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
        input_data = {
            "keyword": payload.keyword,
            "channels": payload.channels,
            "time_range": payload.time_range,
            "sort_by": payload.sort_by,
            "max_results_per_channel": payload.max_results_per_channel,
        }
        if payload.budget is not None:
            input_data["budget"] = payload.budget.model_dump()
        job = container.job_repo.create_job(Job(
            job_id=uuid.uuid4().hex[:12],
            job_type="sniffer_search",
            input_json=json.dumps(input_data),
        ))
        result_job = container.job_runner.run(job.job_id)
        if result_job.status == "failed":
            raise HTTPException(status_code=500, detail=result_job.error_message or "Search failed")

        output = json.loads(result_job.output_json or "{}")
        result_ids = output.get("result_ids", [])
        summary = output.get("summary", {})
        results = container.sniffer_repo.get_results_by_ids(result_ids) if result_ids else []
        return SearchResponseOut(
            results=[_result_to_out(r) for r in results],
            summary=SearchSummaryOut(**summary),
        )

    @router.get("/channels", response_model=list[ChannelInfoOut])
    def list_channels() -> list[ChannelInfoOut]:
        channels = container.channel_registry.list_channels()
        return [ChannelInfoOut(**ch) for ch in channels]

    # --- Sniffer Run History ---

    @router.get("/runs", response_model=list[SnifferRunOut])
    def list_sniffer_runs(limit: int = 50):
        runs = container.job_repo.list_sniffer_runs(limit=max(1, min(limit, 200)))
        return [SnifferRunOut(
            run_id=r.run_id, job_id=r.job_id, query_json=r.query_json,
            pack_id=r.pack_id, status=r.status, result_count=r.result_count,
            channels_used=r.channels_used, error_message=r.error_message,
            started_at=r.started_at, finished_at=r.finished_at,
            metadata=r.metadata,
        ) for r in runs]

    @router.get("/runs/{run_id}")
    def get_sniffer_run(run_id: str):
        run = container.job_repo.get_sniffer_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        # Events are stored under job_id (RunContext.run_id), not sniffer run_id
        events = container.job_repo.list_events(run.job_id)
        return {
            "run": SnifferRunOut(
                run_id=run.run_id, job_id=run.job_id, query_json=run.query_json,
                pack_id=run.pack_id, status=run.status, result_count=run.result_count,
                channels_used=run.channels_used, error_message=run.error_message,
                started_at=run.started_at, finished_at=run.finished_at,
                metadata=run.metadata,
            ),
            "events": [ProvenanceEventOut(
                event_id=e.event_id, run_id=e.run_id, event_type=e.event_type,
                actor=e.actor, entity_refs=e.entity_refs, payload=e.payload, ts=e.ts,
            ) for e in events],
        }

    # --- P1-1: Deep analyze ---

    @router.post("/results/{result_id}/deep-analyze", response_model=ResourceAnalysisOut)
    def deep_analyze(result_id: str):
        sr = container.sniffer_repo.get_result(result_id)
        if not sr:
            raise HTTPException(status_code=404, detail="Result not found")
        container.job_repo.append_event(ProvenanceEvent(
            event_id=uuid.uuid4().hex[:12], run_id=result_id,
            event_type="DeepAnalyzeStarted", actor="user",
            entity_refs={"result_id": result_id},
        ))
        from core.pipeline.stages import canonicalize_url, make_resource_id
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
        container.resource_repo.upsert(resource)
        analysis = container.article_agent.analyze(resource)
        container.job_repo.append_event(ProvenanceEvent(
            event_id=uuid.uuid4().hex[:12], run_id=result_id,
            event_type="DeepAnalyzeFinished", actor="system",
            entity_refs={"result_id": result_id, "resource_id": analysis.resource_id},
        ))
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
        from core.pipeline.stages import canonicalize_url, make_resource_id
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
        container.resource_repo.upsert(resource)
        container.kb_repo.add_item(payload.kb_id, resource.resource_id)
        container.job_repo.append_event(ProvenanceEvent(
            event_id=uuid.uuid4().hex[:12], run_id=result_id,
            event_type="SavedToKB", actor="user",
            entity_refs={"result_id": result_id, "resource_id": resource.resource_id, "kb_id": payload.kb_id},
        ))
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
        container.job_repo.append_event(ProvenanceEvent(
            event_id=uuid.uuid4().hex[:12], run_id=result_id,
            event_type="ConvertedToSource", actor="user",
            entity_refs={"result_id": result_id, "source_id": source.source_id},
        ))
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
        pack = container.sniffer_repo.get_pack(pack_id)
        if not pack:
            raise HTTPException(status_code=404, detail="Pack not found")

        q_data = json.loads(pack.query_json)
        input_data = {
            "keyword": q_data.get("keyword", ""),
            "channels": q_data.get("channels", []),
            "time_range": q_data.get("time_range", "all"),
            "sort_by": q_data.get("sort_by", "relevance"),
            "max_results_per_channel": q_data.get("max_results_per_channel", 10),
            "pack_id": pack_id,
        }
        job = container.job_repo.create_job(Job(
            job_id=uuid.uuid4().hex[:12],
            job_type="sniffer_search",
            input_json=json.dumps(input_data),
        ))
        result_job = container.job_runner.run(job.job_id)
        if result_job.status == "failed":
            raise HTTPException(status_code=500, detail=result_job.error_message or "Pack run failed")

        output = json.loads(result_job.output_json or "{}")
        result_ids = output.get("result_ids", [])
        summary = output.get("summary", {})
        results = container.sniffer_repo.get_results_by_ids(result_ids) if result_ids else []
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
        # Sync to unified scheduler
        if hasattr(container, "scheduler") and container.scheduler:
            from core.runner.scheduler import _INTERVAL_MAP
            interval = _INTERVAL_MAP.get(payload.schedule_cron or "") if payload.schedule_cron else None
            container.scheduler.reschedule(
                "sniffer_pack", pack_id, interval, enabled=bool(payload.schedule_cron),
            )
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
