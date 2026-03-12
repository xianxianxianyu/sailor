from __future__ import annotations

import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Response

from backend.app.container import AppContainer
from backend.app.schemas import (
  ChannelHealthOut,
  ChannelInfoOut,
  CompareIn,
  CompareSummaryOut,
  ConvertSourceIn,
  ConvertSourceOut,
  CreateSnifferPackIn,
  ImportPackIn,
  JobAcceptedOut,
  ProvenanceEventOut,
  ResourceAnalysisOut,
  SaveToKBIn,
  SaveToKBOut,
  SearchResponseOut,
  SearchSummaryOut,
  SniffQueryIn,
  SniffResultOut,
  SnifferPackFullOut,
    SnifferRunOut,
    UpdatePackScheduleIn,
)
from core.models import Job, ProvenanceEvent, Resource, SniffQuery, SourceRecord

router = APIRouter(prefix="/sniffer", tags=["system"])


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
    def search(
        payload: SniffQueryIn,
        response: Response,
        wait: bool = Query(True),
        timeout: int = Query(60),
    ) -> SearchResponseOut:
        from backend.app.utils import wait_for_job
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

        if not wait:
            return SearchResponseOut(job_id=job.job_id, status=job.status, results=[], summary=SearchSummaryOut(
                total=0, keyword=payload.keyword, channel_distribution={},
                keyword_clusters=[], time_distribution={}, top_by_engagement=[],
            ))

        result_job = wait_for_job(container.job_repo, job.job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
            return SearchResponseOut(
                job_id=result_job.job_id,
                status=result_job.status,
                results=[],
                summary=SearchSummaryOut(
                    total=0,
                    keyword=payload.keyword,
                    channel_distribution={},
                    keyword_clusters=[],
                    time_distribution={},
                    top_by_engagement=[],
                ),
            )
        if result_job.status in ("failed", "cancelled"):
            return SearchResponseOut(
                job_id=result_job.job_id,
                status=result_job.status,
                error_message=result_job.error_message or ("Search failed" if result_job.status == "failed" else None),
                results=[],
                summary=SearchSummaryOut(
                    total=0,
                    keyword=payload.keyword,
                    channel_distribution={},
                    keyword_clusters=[],
                    time_distribution={},
                    top_by_engagement=[],
                ),
            )

        output = json.loads(result_job.output_json or "{}")
        result_ids = output.get("result_ids", [])
        summary = output.get("summary", {})
        results = container.sniffer_repo.get_results_by_ids(result_ids) if result_ids else []
        return SearchResponseOut(
            job_id=result_job.job_id,
            status=result_job.status,
            results=[_result_to_out(r) for r in results],
            summary=SearchSummaryOut(**summary),
        )

    @router.get("/jobs/{job_id}", response_model=SearchResponseOut)
    def get_search_job_result(job_id: str, response: Response) -> SearchResponseOut:
        """根据 job_id 取回 sniffer_search 的最终结果（供 202 轮询链路取回）。"""
        job = container.job_repo.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.job_type != "sniffer_search":
            raise HTTPException(status_code=400, detail="Not a sniffer_search job")

        keyword = ""
        try:
            keyword = str(json.loads(job.input_json or "{}").get("keyword") or "")
        except Exception:
            keyword = ""

        empty_summary = SearchSummaryOut(
            total=0,
            keyword=keyword,
            channel_distribution={},
            keyword_clusters=[],
            time_distribution={},
            top_by_engagement=[],
        )

        # Not ready yet
        if job.status in ("queued", "running"):
            response.status_code = 202
            response.headers["Location"] = f"/jobs/{job_id}"
            response.headers["Retry-After"] = "2"
            return SearchResponseOut(
                job_id=job_id,
                status=job.status,
                error_message=job.error_message,
                results=[],
                summary=empty_summary,
            )

        # Terminal but not succeeded
        if job.status in ("failed", "cancelled"):
            return SearchResponseOut(
                job_id=job_id,
                status=job.status,
                error_message=job.error_message,
                results=[],
                summary=empty_summary,
            )

        output = json.loads(job.output_json or "{}")
        result_ids = output.get("result_ids", [])
        summary = output.get("summary", {})
        results = container.sniffer_repo.get_results_by_ids(result_ids) if result_ids else []
        try:
            summary_out = SearchSummaryOut(**summary)
        except Exception:
            summary_out = empty_summary

        return SearchResponseOut(
            job_id=job_id,
            status=job.status,
            results=[_result_to_out(r) for r in results],
            summary=summary_out,
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

    @router.post("/results/{result_id}/deep-analyze", response_model=ResourceAnalysisOut | JobAcceptedOut)
    def deep_analyze(
        result_id: str,
        response: Response,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> ResourceAnalysisOut | JobAcceptedOut:
        from backend.app.utils import wait_for_job
        from core.models import Job
        sr = container.sniffer_repo.get_result(result_id)
        if not sr:
            raise HTTPException(status_code=404, detail="Result not found")

        job_id = uuid.uuid4().hex[:12]
        container.job_repo.create_job(Job(
            job_id=job_id,
            job_type="sniffer_deep_analyze",
            input_json=json.dumps({"result_id": result_id}),
        ))

        if not wait:
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status="queued")

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status=result_job.status)
        if result_job.status in ("failed", "cancelled"):
            return JobAcceptedOut(
                job_id=job_id,
                status=result_job.status,
                error_message=result_job.error_message or ("Deep analyze failed" if result_job.status == "failed" else None),
            )

        output = json.loads(result_job.output_json or "{}")
        resource_id = output.get("resource_id")
        if not resource_id:
            raise HTTPException(status_code=500, detail={
                "job_id": job_id,
                "status": "succeeded",
                "error_message": "Missing resource_id in job output",
            })

        analysis = container.analysis_repo.get_by_resource_id(resource_id)
        if not analysis:
            raise HTTPException(status_code=500, detail={
                "job_id": job_id,
                "status": "succeeded",
                "error_message": "Analysis not found",
            })

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

    @router.post("/results/{result_id}/save-to-kb", response_model=SaveToKBOut | JobAcceptedOut)
    def save_to_kb(
        result_id: str,
        payload: SaveToKBIn,
        response: Response,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> SaveToKBOut | JobAcceptedOut:
        from backend.app.utils import wait_for_job
        sr = container.sniffer_repo.get_result(result_id)
        if not sr:
            raise HTTPException(status_code=404, detail="Result not found")
        kb = container.kb_repo.get_kb(payload.kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        job_id = uuid.uuid4().hex[:12]
        container.job_repo.create_job(Job(
            job_id=job_id,
            job_type="sniffer_save_to_kb",
            input_json=json.dumps({"result_id": result_id, "kb_id": payload.kb_id}),
        ))

        if not wait:
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status="queued")

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status=result_job.status)
        if result_job.status in ("failed", "cancelled"):
            return JobAcceptedOut(
                job_id=job_id,
                status=result_job.status,
                error_message=result_job.error_message or ("Save to KB failed" if result_job.status == "failed" else None),
            )

        output = json.loads(result_job.output_json or "{}")
        resource_id = output.get("resource_id")
        kb_id = output.get("kb_id")
        if not resource_id or not kb_id:
            raise HTTPException(status_code=500, detail={
                "job_id": job_id,
                "status": "succeeded",
                "error_message": "Missing resource_id/kb_id in job output",
            })
        return SaveToKBOut(saved=True, resource_id=resource_id, kb_id=kb_id)

    # --- P1-3: Convert to source ---

    @router.post("/results/{result_id}/convert-source", response_model=ConvertSourceOut | JobAcceptedOut)
    def convert_source(
        result_id: str,
        payload: ConvertSourceIn,
        response: Response,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> ConvertSourceOut | JobAcceptedOut:
        from backend.app.utils import wait_for_job
        sr = container.sniffer_repo.get_result(result_id)
        if not sr:
            raise HTTPException(status_code=404, detail="Result not found")

        job_id = uuid.uuid4().hex[:12]
        container.job_repo.create_job(Job(
            job_id=job_id,
            job_type="sniffer_convert_source",
            input_json=json.dumps({
                "result_id": result_id,
                "name": payload.name,
                "source_type": payload.source_type,
            }),
        ))

        if not wait:
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status="queued")

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status=result_job.status)
        if result_job.status in ("failed", "cancelled"):
            return JobAcceptedOut(
                job_id=job_id,
                status=result_job.status,
                error_message=result_job.error_message or ("Convert to source failed" if result_job.status == "failed" else None),
            )

        output = json.loads(result_job.output_json or "{}")
        source_id = output.get("source_id")
        if not source_id:
            raise HTTPException(status_code=500, detail={
                "job_id": job_id,
                "status": "succeeded",
                "error_message": "Missing source_id in job output",
            })
        return ConvertSourceOut(converted=True, source_id=source_id)

    # --- P1-2: Compare ---

    @router.post("/compare", response_model=CompareSummaryOut | JobAcceptedOut)
    def compare(
        payload: CompareIn,
        response: Response,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> CompareSummaryOut | JobAcceptedOut:
        from backend.app.utils import wait_for_job
        from core.models import Job
        if len(payload.result_ids) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 results to compare")

        job_id = uuid.uuid4().hex[:12]
        container.job_repo.create_job(Job(
            job_id=job_id,
            job_type="sniffer_compare",
            input_json=json.dumps({"result_ids": payload.result_ids}),
        ))

        if not wait:
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status="queued")

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
            return JobAcceptedOut(job_id=job_id, status=result_job.status)
        if result_job.status in ("failed", "cancelled"):
            return JobAcceptedOut(
                job_id=job_id,
                status=result_job.status,
                error_message=result_job.error_message or ("Compare failed" if result_job.status == "failed" else None),
            )

        output = json.loads(result_job.output_json or "{}")
        return CompareSummaryOut(
            dimensions=output.get("dimensions") or [],
            verdict=str(output.get("verdict") or ""),
            model=str(output.get("model") or ""),
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
    def run_pack(
        pack_id: str,
        response: Response,
        wait: bool = Query(True),
        timeout: int = Query(60),
    ):
        from backend.app.utils import wait_for_job
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

        if not wait:
            return SearchResponseOut(job_id=job.job_id, status=job.status, results=[], summary=SearchSummaryOut(
                total=0, keyword=input_data["keyword"], channel_distribution={},
                keyword_clusters=[], time_distribution={}, top_by_engagement=[],
            ))

        result_job = wait_for_job(container.job_repo, job.job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
            return SearchResponseOut(
                job_id=result_job.job_id,
                status=result_job.status,
                results=[],
                summary=SearchSummaryOut(
                    total=0,
                    keyword=input_data["keyword"],
                    channel_distribution={},
                    keyword_clusters=[],
                    time_distribution={},
                    top_by_engagement=[],
                ),
            )
        if result_job.status in ("failed", "cancelled"):
            return SearchResponseOut(
                job_id=result_job.job_id,
                status=result_job.status,
                error_message=result_job.error_message or ("Pack run failed" if result_job.status == "failed" else None),
                results=[],
                summary=SearchSummaryOut(
                    total=0,
                    keyword=input_data["keyword"],
                    channel_distribution={},
                    keyword_clusters=[],
                    time_distribution={},
                    top_by_engagement=[],
                ),
            )

        output = json.loads(result_job.output_json or "{}")
        result_ids = output.get("result_ids", [])
        summary = output.get("summary", {})
        results = container.sniffer_repo.get_results_by_ids(result_ids) if result_ids else []
        return SearchResponseOut(
            job_id=result_job.job_id,
            status=result_job.status,
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
