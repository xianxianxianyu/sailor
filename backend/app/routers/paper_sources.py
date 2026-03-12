"""Paper Engine API Router (Module 6)

对外 API 统一入口
"""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Response

from backend.app.container import AppContainer
from backend.app.schemas_paper import (
    CreatePaperSourceIn,
    PaperOut,
    PaperRunOut,
    PaperSourceOut,
    RunPaperSourceOut,
    UpdatePaperSourceIn,
)
from core.models import Job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paper-sources", tags=["papers"])
papers_router = APIRouter(prefix="/papers", tags=["papers"])


def mount_paper_routes(container: AppContainer) -> list[APIRouter]:
    """Mount paper engine routes"""

    # ========== Module 1: Paper Source CRUD ==========

    @router.get("", response_model=list[PaperSourceOut])
    def list_paper_sources(
        platform: str | None = None,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaperSourceOut]:
        """列出 paper sources"""
        sources = container.paper_repo.list_sources(
            platform=platform,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )
        return [
            PaperSourceOut(
                source_id=s.source_id,
                platform=s.platform,
                endpoint=s.endpoint,
                name=s.name,
                config=json.loads(s.config_json),
                cursor=json.loads(s.cursor_json) if s.cursor_json else None,
                enabled=s.enabled,
                schedule_minutes=s.schedule_minutes,
                last_run_at=s.last_run_at,
                error_count=s.error_count,
                last_error=s.last_error,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sources
        ]

    @router.post("", response_model=PaperSourceOut)
    def create_paper_source(data: CreatePaperSourceIn) -> PaperSourceOut:
        """创建 paper source"""
        source = container.paper_repo.upsert_source(
            source_id=data.source_id,
            platform=data.platform,
            endpoint=data.endpoint,
            name=data.name,
            config_json=json.dumps(data.config),
            cursor_json=json.dumps(data.cursor) if data.cursor else None,
            enabled=data.enabled,
            schedule_minutes=data.schedule_minutes,
        )
        return PaperSourceOut(
            source_id=source.source_id,
            platform=source.platform,
            endpoint=source.endpoint,
            name=source.name,
            config=json.loads(source.config_json),
            cursor=json.loads(source.cursor_json) if source.cursor_json else None,
            enabled=source.enabled,
            schedule_minutes=source.schedule_minutes,
            last_run_at=source.last_run_at,
            error_count=source.error_count,
            last_error=source.last_error,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    @router.get("/{source_id}", response_model=PaperSourceOut)
    def get_paper_source(source_id: str) -> PaperSourceOut:
        """获取单个 paper source"""
        source = container.paper_repo.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Paper source not found")

        return PaperSourceOut(
            source_id=source.source_id,
            platform=source.platform,
            endpoint=source.endpoint,
            name=source.name,
            config=json.loads(source.config_json),
            cursor=json.loads(source.cursor_json) if source.cursor_json else None,
            enabled=source.enabled,
            schedule_minutes=source.schedule_minutes,
            last_run_at=source.last_run_at,
            error_count=source.error_count,
            last_error=source.last_error,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    @router.patch("/{source_id}", response_model=PaperSourceOut)
    def update_paper_source(
        source_id: str, data: UpdatePaperSourceIn
    ) -> PaperSourceOut:
        """更新 paper source"""
        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.config is not None:
            updates["config_json"] = json.dumps(data.config)
        if data.cursor is not None:
            updates["cursor_json"] = json.dumps(data.cursor)
        if data.enabled is not None:
            updates["enabled"] = 1 if data.enabled else 0
        if data.schedule_minutes is not None:
            updates["schedule_minutes"] = data.schedule_minutes

        source = container.paper_repo.update_source(source_id, **updates)
        if not source:
            raise HTTPException(status_code=404, detail="Paper source not found")

        return PaperSourceOut(
            source_id=source.source_id,
            platform=source.platform,
            endpoint=source.endpoint,
            name=source.name,
            config=json.loads(source.config_json),
            cursor=json.loads(source.cursor_json) if source.cursor_json else None,
            enabled=source.enabled,
            schedule_minutes=source.schedule_minutes,
            last_run_at=source.last_run_at,
            error_count=source.error_count,
            last_error=source.last_error,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    @router.delete("/{source_id}")
    def delete_paper_source(source_id: str) -> dict[str, str]:
        """删除 paper source"""
        success = container.paper_repo.delete_source(source_id)
        if not success:
            raise HTTPException(status_code=404, detail="Paper source not found")
        return {"status": "deleted"}

    # ========== Module 2: Paper Read ==========

    @papers_router.get("", response_model=list[PaperOut])
    def list_papers(limit: int = 50, offset: int = 0) -> list[PaperOut]:
        """列出 papers"""
        papers = container.paper_repo.list_papers(limit=limit, offset=offset)
        return [
            PaperOut(
                paper_id=p.paper_id,
                canonical_id=p.canonical_id,
                canonical_url=p.canonical_url,
                title=p.title,
                abstract=p.abstract,
                published_at=p.published_at,
                authors=json.loads(p.authors_json) if p.authors_json else None,
                venue=p.venue,
                doi=p.doi,
                pdf_url=p.pdf_url,
                external_ids=(
                    json.loads(p.external_ids_json) if p.external_ids_json else None
                ),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in papers
        ]

    @papers_router.get("/{paper_id}", response_model=PaperOut)
    def get_paper(paper_id: str) -> PaperOut:
        """获取单个 paper"""
        paper = container.paper_repo.get_paper(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")

        return PaperOut(
            paper_id=paper.paper_id,
            canonical_id=paper.canonical_id,
            canonical_url=paper.canonical_url,
            title=paper.title,
            abstract=paper.abstract,
            published_at=paper.published_at,
            authors=json.loads(paper.authors_json) if paper.authors_json else None,
            venue=paper.venue,
            doi=paper.doi,
            pdf_url=paper.pdf_url,
            external_ids=(
                json.loads(paper.external_ids_json)
                if paper.external_ids_json
                else None
            ),
            created_at=paper.created_at,
            updated_at=paper.updated_at,
        )

    # ========== Module 3: Papers by Source ==========

    @router.get("/{source_id}/papers", response_model=list[PaperOut])
    def list_papers_by_source(
        source_id: str, limit: int = 50, offset: int = 0
    ) -> list[PaperOut]:
        """列出某 source 采集过的 papers"""
        papers = container.paper_repo.list_papers_by_source(
            source_id, limit=limit, offset=offset
        )
        return [
            PaperOut(
                paper_id=p.paper_id,
                canonical_id=p.canonical_id,
                canonical_url=p.canonical_url,
                title=p.title,
                abstract=p.abstract,
                published_at=p.published_at,
                authors=json.loads(p.authors_json) if p.authors_json else None,
                venue=p.venue,
                doi=p.doi,
                pdf_url=p.pdf_url,
                external_ids=(
                    json.loads(p.external_ids_json) if p.external_ids_json else None
                ),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in papers
        ]

    # ========== Module 4: Runs ==========

    @router.get("/{source_id}/runs", response_model=list[PaperRunOut])
    def list_paper_runs(
        source_id: str, limit: int = 20, offset: int = 0
    ) -> list[PaperRunOut]:
        """列出某 source 的 run 历史"""
        runs = container.paper_repo.list_runs(source_id, limit=limit, offset=offset)
        return [
            PaperRunOut(
                run_id=r.run_id,
                source_id=r.source_id,
                job_id=r.job_id,
                status=r.status,
                started_at=r.started_at,
                finished_at=r.finished_at,
                fetched_count=r.fetched_count,
                processed_count=r.processed_count,
                error_message=r.error_message,
                metrics=json.loads(r.metrics_json) if r.metrics_json else None,
                cursor_before=(
                    json.loads(r.cursor_before_json) if r.cursor_before_json else None
                ),
                cursor_after=(
                    json.loads(r.cursor_after_json) if r.cursor_after_json else None
                ),
            )
            for r in runs
        ]

    # ========== Module 5: Trigger Sync ==========

    @router.post("/{source_id}/run", response_model=RunPaperSourceOut)
    def run_paper_source(
        source_id: str,
        response: Response,
        wait: bool = Query(False),
        timeout: int = Query(120),
    ) -> RunPaperSourceOut:
        """触发 paper source 同步"""
        from backend.app.utils import wait_for_job
        source = container.paper_repo.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Paper source not found")

        if not source.enabled:
            raise HTTPException(status_code=400, detail="Paper source is disabled")

        job_id = uuid.uuid4().hex[:12]
        container.job_repo.create_job(
            Job(
                job_id=job_id,
                job_type="paper_source_run",
                input_json=json.dumps({"source_id": source_id}),
            )
        )

        logger.info("[paper] 触发同步: source=%s, job=%s", source_id, job_id)

        if not wait:
            # P0-5: run_id 对齐 job_id（即使尚未执行，也可稳定用于追溯）
            return RunPaperSourceOut(run_id=job_id, source_id=source_id, job_id=job_id, status="queued")

        result_job = wait_for_job(container.job_repo, job_id, timeout)
        if result_job.status in ("queued", "running"):
            response.status_code = 202
            return RunPaperSourceOut(
                run_id=job_id,
                source_id=source_id,
                job_id=job_id,
                status=result_job.status,
            )
        output = json.loads(result_job.output_json or "{}")
        return RunPaperSourceOut(
            run_id=output.get("run_id", ""),
            source_id=source_id,
            job_id=job_id,
            status=result_job.status,
        )

    return [router, papers_router]
