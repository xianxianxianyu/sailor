"""Paper Source Handler (Module 5: Execution Bridge)

执行桥接：连接数据层与逻辑层
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from core.models import Job
from core.runner.handlers import JobHandler, RunContext

from .models import PaperSyncResult
from .port import PaperSyncPort
from .repository import PaperRepository
from .tools import paper_fetch_arxiv_atom, paper_fetch_openreview_notes

logger = logging.getLogger(__name__)


class PaperSourceHandler(JobHandler):
    """Paper source run handler（模块 5）"""

    def __init__(self, paper_repo: PaperRepository, sync_port: PaperSyncPort):
        self.paper_repo = paper_repo
        self.sync_port = sync_port

    def execute(self, job: Job, ctx: RunContext) -> str:
        """
        执行 paper source 同步

        Job input_json 格式:
        {
            "source_id": "paper_arxiv_abc123"
        }

        Returns:
            JSON string with run_id and counts
        """
        input_data = json.loads(job.input_json)
        source_id = input_data["source_id"]

        logger.info("[paper] 开始同步 source: %s", source_id)

        # 1. 读取 source
        source = self.paper_repo.get_source(source_id)
        if not source:
            raise ValueError(f"Paper source not found: {source_id}")

        if not source.enabled:
            raise ValueError(f"Paper source is disabled: {source_id}")

        # 2. 创建 run 记录
        run_id = self.paper_repo.create_run(source_id, job.job_id)
        cursor_before = json.loads(source.cursor_json) if source.cursor_json else None

        try:
            # 3. Tool Functions：HTTP acquisition + raw capture（必须可回放）
            logger.info("[paper] HTTP acquisition: platform=%s", source.platform)
            if source.platform == "arxiv":
                capture_id, raw = paper_fetch_arxiv_atom(ctx, source)
            elif source.platform == "openreview":
                capture_id, raw = paper_fetch_openreview_notes(ctx, source)
            else:
                raise ValueError(f"Unsupported platform: {source.platform}")

            ctx.emit_event(
                "PaperRawCaptured",
                payload={"platform": source.platform, "capture_id": capture_id},
                entity_refs={"source_id": source_id, "capture_id": capture_id},
            )

            # 4. 逻辑层：纯解析/归一化（无网络 I/O）
            logger.info("[paper] normalize: platform=%s", source.platform)
            result: PaperSyncResult = self.sync_port.sync(source, raw)

            # 5. 落库 papers + source_items
            processed_count = 0
            seen_at = datetime.utcnow()

            for paper_record in result.papers:
                paper_id = self.paper_repo.upsert_paper(paper_record)
                self.paper_repo.mark_seen(
                    source_id, paper_record.item_key, paper_id, seen_at
                )
                processed_count += 1

            # 6. 更新 source 状态（成功复位与 cursor 是否为空无关，P0-6）
            source_updates: dict[str, object] = {
                "last_run_at": datetime.utcnow().isoformat(),
                "error_count": 0,
                "last_error": None,
            }
            if result.next_cursor_json is not None:
                source_updates["cursor_json"] = json.dumps(result.next_cursor_json)
            self.paper_repo.update_source(source_id, **source_updates)

            # 7. 完成 run
            self.paper_repo.finish_run(
                run_id=run_id,
                status="succeeded",
                fetched_count=len(result.papers),
                processed_count=processed_count,
                cursor_before=cursor_before,
                cursor_after=result.next_cursor_json,
                metrics=result.metrics_json,
            )

            logger.info(
                "[paper] 同步完成: source=%s, fetched=%d, processed=%d",
                source_id,
                len(result.papers),
                processed_count,
            )

            return json.dumps(
                {
                    "run_id": run_id,
                    "source_id": source_id,
                    "fetched_count": len(result.papers),
                    "processed_count": processed_count,
                }
            )

        except Exception as e:
            logger.exception("[paper] 同步失败: source=%s", source_id)

            # 更新 source error 状态
            self.paper_repo.record_source_error(source_id, str(e))

            # 完成 run（失败）
            self.paper_repo.finish_run(
                run_id=run_id,
                status="failed",
                error_message=str(e),
            )

            raise
