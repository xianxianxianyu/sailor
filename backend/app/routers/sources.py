from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import logging
from pathlib import Path
from typing import Any
import uuid

from fastapi import APIRouter, HTTPException

from backend.app.container import AppContainer
from backend.app.schemas import (
    CreateSourceIn,
    ImportSourcesIn,
    ImportSourcesOut,
    RunBatchOut,
    RunSourceOut,
    SourceOut,
    SourceResourceOut,
    SourceRunOut,
    SourceStatusOut,
    UpdateSourceIn,
)
from core.models import Job, SourceRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])


def mount_source_routes(container: AppContainer) -> APIRouter:
    @router.get("", response_model=list[SourceOut])
    def list_sources(source_type: str | None = None, enabled_only: bool = False) -> list[SourceOut]:
        sources = container.source_repo.list_sources(source_type=source_type, enabled_only=enabled_only)
        return [SourceOut.model_validate(asdict(s)) for s in sources]

    @router.post("", response_model=SourceOut)
    def create_source(payload: CreateSourceIn) -> SourceOut:
        endpoint = payload.endpoint
        source_id = payload.source_id or _make_source_id(payload.source_type, endpoint, payload.name)
        source = SourceRecord(
            source_id=source_id,
            source_type=payload.source_type,
            name=payload.name,
            endpoint=endpoint,
            config=payload.config,
            enabled=payload.enabled,
            schedule_minutes=max(payload.schedule_minutes, 1),
        )
        created = container.source_repo.upsert_source(source)
        return SourceOut.model_validate(asdict(created))

    @router.patch("/{source_id}", response_model=SourceOut)
    def update_source(source_id: str, payload: UpdateSourceIn) -> SourceOut:
        updated = container.source_repo.update_source(
            source_id,
            name=payload.name,
            endpoint=payload.endpoint,
            config=payload.config,
            enabled=payload.enabled,
            schedule_minutes=max(payload.schedule_minutes, 1) if payload.schedule_minutes is not None else None,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Source not found")
        return SourceOut.model_validate(asdict(updated))

    @router.delete("/{source_id}")
    def delete_source(source_id: str) -> dict[str, bool]:
        deleted = container.source_repo.delete_source(source_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Source not found")
        return {"deleted": True}

    @router.get("/status", response_model=SourceStatusOut)
    def source_status() -> SourceStatusOut:
        return SourceStatusOut.model_validate(container.source_repo.get_status_summary())

    @router.get("/{source_id}/runs", response_model=list[SourceRunOut])
    def list_runs(source_id: str, limit: int = 20) -> list[SourceRunOut]:
        runs = container.source_repo.list_runs(source_id, limit=max(1, min(limit, 200)))
        return [SourceRunOut.model_validate(asdict(run)) for run in runs]

    @router.post("/import-local", response_model=ImportSourcesOut)
    def import_local_config(payload: ImportSourcesIn) -> ImportSourcesOut:
        config_path = _resolve_config_path(container, payload.config_file)
        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")

        logger.info("[sources] 开始导入本地配置: %s", config_path)
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"配置文件 JSON 无效: {exc}") from exc

        defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
        source_items = data.get("sources")
        if not isinstance(source_items, list):
            raise HTTPException(status_code=400, detail="配置文件必须包含 sources 数组")

        imported = 0
        rss_rows: list[dict[str, Any]] = []
        for item in source_items:
            if not isinstance(item, dict):
                continue

            source_type = str(item.get("source_type") or defaults.get("source_type") or "rss")
            endpoint = item.get("endpoint") or item.get("xml_url") or item.get("url")
            endpoint = str(endpoint) if endpoint else None
            name = str(item.get("name") or endpoint or "Unnamed Source")
            source_id = str(item.get("source_id") or _make_source_id(source_type, endpoint, name))

            schedule_raw = item.get("schedule_minutes", item.get("poll_minutes", defaults.get("poll_minutes", 30)))
            schedule_minutes = max(_coerce_int(schedule_raw, 30), 1)
            enabled = bool(item.get("enabled", defaults.get("enabled", True)))

            config = dict(item.get("config") or {})
            for key in ("xml_url", "html_url", "url", "tags", "poll_minutes", "schedule_minutes"):
                if key in item and key not in config:
                    config[key] = item[key]

            container.source_repo.upsert_source(
                SourceRecord(
                    source_id=source_id,
                    source_type=source_type,
                    name=name,
                    endpoint=endpoint,
                    config=config,
                    enabled=enabled,
                    schedule_minutes=schedule_minutes,
                )
            )
            imported += 1

            if source_type == "rss":
                xml_url = str(item.get("xml_url") or endpoint or "")
                if xml_url:
                    rss_rows.append(
                        {
                            "name": name,
                            "xml_url": xml_url,
                            "html_url": str(item.get("html_url")) if item.get("html_url") else None,
                        }
                    )

        rss_synced = container.feed_repo.import_feeds(rss_rows) if rss_rows else 0
        logger.info("[sources] 导入完成: 导入 %d 个 source, 同步 %d 个 RSS feed", imported, rss_synced)
        return ImportSourcesOut(imported=imported, rss_synced=rss_synced, total_parsed=len(source_items))

    @router.post("/{source_id}/run", response_model=RunSourceOut)
    def run_source(source_id: str) -> RunSourceOut:
        source = container.source_repo.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        logger.info("[sources] 开始运行 source: %s (%s)", source_id, source.name)

        job = container.job_repo.create_job(Job(
            job_id=uuid.uuid4().hex[:16],
            job_type="source_run",
            input_json=json.dumps({"source_id": source_id}),
        ))
        result_job = container.job_runner.run(job.job_id)

        if result_job.status == "failed":
            logger.error("[sources] source: %s 失败: %s", source_id, result_job.error_message)
            raise HTTPException(status_code=500, detail=f"Source run failed: {result_job.error_message}")

        output = json.loads(result_job.output_json or "{}")
        logger.info("[sources] 完成 source: %s, 获取 %d 条, 处理 %d 条", source_id, output.get('fetched_count', 0), output.get('processed_count', 0))

        return RunSourceOut(
            run_id=output.get("source_run_id", ""),
            source_id=source_id,
            status="success",
            fetched_count=output.get("fetched_count", 0),
            processed_count=output.get("processed_count", 0),
        )

    @router.post("/run-by-type/{source_type}", response_model=RunBatchOut)
    def run_sources_by_type(source_type: str, enabled_only: bool = True) -> RunBatchOut:
        """按类型批量运行所有源"""
        sources = container.source_repo.list_sources(source_type=source_type, enabled_only=enabled_only)
        if not sources:
            raise HTTPException(status_code=404, detail=f"No sources found for type: {source_type}")

        logger.info("[sources] 开始批量运行 source_type=%s, 共 %d 个源", source_type, len(sources))

        success_count = 0
        failed_count = 0
        total_fetched = 0
        total_processed = 0

        for source in sources:
            try:
                job = container.job_repo.create_job(Job(
                    job_id=uuid.uuid4().hex[:16],
                    job_type="source_run",
                    input_json=json.dumps({"source_id": source.source_id}),
                ))
                result_job = container.job_runner.run(job.job_id)

                if result_job.status == "failed":
                    failed_count += 1
                    logger.error("[sources] source=%s 失败: %s", source.name, result_job.error_message)
                else:
                    output = json.loads(result_job.output_json or "{}")
                    success_count += 1
                    total_fetched += output.get("fetched_count", 0)
                    total_processed += output.get("processed_count", 0)
                    logger.info("[sources] source=%s 完成, 获取 %d 条", source.name, output.get('fetched_count', 0))

            except Exception as e:
                failed_count += 1
                logger.error("[sources] source=%s 失败: %s", source.name, e)

        logger.info("[sources] 批量运行完成: 成功 %d, 失败 %d, 共获取 %d 条", success_count, failed_count, total_fetched)

        return RunBatchOut(
            source_type=source_type,
            total_sources=len(sources),
            success_count=success_count,
            failed_count=failed_count,
            total_fetched=total_fetched,
            total_processed=total_processed,
        )

    @router.get("/{source_id}/resources", response_model=list[SourceResourceOut])
    def get_source_resources(source_id: str, limit: int = 50, offset: int = 0) -> list[SourceResourceOut]:
        """获取统一源的最近抓取内容"""
        logger.info("[sources] get_source_resources called: source_id=%s, limit=%d", source_id, limit)
        items = container.source_repo.list_source_resources(source_id, limit, offset)
        logger.info("[sources] list_source_resources returned %d items for source_id=%s", len(items), source_id)
        result = []
        for item in items:
            result.append(SourceResourceOut(
                resource_id=item.resource_id,
                canonical_url=item.canonical_url,
                source=item.source,
                title=item.title,
                published_at=item.published_at,
                text=item.text,
                original_url=item.original_url,
                topics=item.topics,
                summary=item.summary,
                last_seen_at=item.last_seen_at,
            ))
        return result

    return router


def _resolve_config_path(container: AppContainer, config_file: str | None) -> Path:
    base_dir = container.settings.opml_file.parent
    chosen = Path(config_file) if config_file else Path("SailorRSSConfig.json")
    if chosen.is_absolute():
        return chosen
    return (base_dir / chosen).resolve()


def _make_source_id(source_type: str, endpoint: str | None, name: str) -> str:
    key = f"{source_type}:{endpoint or ''}:{name}".encode("utf-8")
    return "src_" + hashlib.sha256(key).hexdigest()[:12]


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

