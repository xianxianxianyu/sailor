from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta

from core.models import Job, Schedule

logger = logging.getLogger(__name__)

_INTERVAL_MAP = {
    "every_1h": 3600,
    "every_6h": 6 * 3600,
    "every_12h": 12 * 3600,
    "every_24h": 24 * 3600,
}


class UnifiedScheduler:
    """DB-backed scheduler — ticks every N seconds, dispatches due jobs."""

    def __init__(self, job_repo, job_runner, sniffer_repo, source_repo,
                 tick_interval: int = 30) -> None:
        self.job_repo = job_repo
        self.job_runner = job_runner
        self.sniffer_repo = sniffer_repo
        self.source_repo = source_repo
        self._tick_interval = tick_interval
        self._stopped = True
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        synced = self.sync_from_config()
        logger.info("[unified-scheduler] Synced %d schedules from config", synced)
        self._stopped = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[unified-scheduler] Started (tick=%ds)", self._tick_interval)

    def stop(self) -> None:
        self._stopped = True

    def sync_from_config(self) -> int:
        """Sync schedules from sniffer_packs + source_registry into schedules table."""
        count = 0
        now = datetime.utcnow()

        # Sniffer packs with schedule_cron
        for pack in self.sniffer_repo.list_scheduled_packs():
            interval = _INTERVAL_MAP.get(pack.schedule_cron or "")
            if not interval:
                continue
            next_run = pack.next_run_at or (now + timedelta(seconds=interval))
            self.job_repo.upsert_schedule(Schedule(
                schedule_id=uuid.uuid4().hex[:12],
                schedule_type="sniffer_pack",
                ref_id=pack.pack_id,
                interval_seconds=interval,
                cron_expr=pack.schedule_cron,
                next_run_at=next_run,
                last_run_at=pack.last_run_at,
                enabled=True,
            ))
            count += 1

        # Enabled sources
        for src in self.source_repo.list_sources(enabled_only=True):
            interval = src.schedule_minutes * 60
            next_run = now + timedelta(seconds=interval)
            if src.last_run_at:
                candidate = src.last_run_at + timedelta(seconds=interval)
                if candidate > now:
                    next_run = candidate
            self.job_repo.upsert_schedule(Schedule(
                schedule_id=uuid.uuid4().hex[:12],
                schedule_type="source_run",
                ref_id=src.source_id,
                interval_seconds=interval,
                next_run_at=next_run,
                last_run_at=src.last_run_at,
                enabled=True,
            ))
            count += 1

        return count

    def reschedule(self, schedule_type: str, ref_id: str,
                   interval_seconds: int | None, enabled: bool = True) -> None:
        """External call: update/create/disable a schedule."""
        if not enabled or not interval_seconds:
            # Try to find and disable existing
            with self.job_repo.db.connect() as conn:
                conn.execute(
                    "UPDATE schedules SET enabled = 0 WHERE schedule_type = ? AND ref_id = ?",
                    (schedule_type, ref_id),
                )
            return
        now = datetime.utcnow()
        self.job_repo.upsert_schedule(Schedule(
            schedule_id=uuid.uuid4().hex[:12],
            schedule_type=schedule_type,
            ref_id=ref_id,
            interval_seconds=interval_seconds,
            next_run_at=now + timedelta(seconds=interval_seconds),
            enabled=True,
        ))

    def _loop(self) -> None:
        while not self._stopped:
            try:
                self._tick()
            except Exception:
                logger.exception("[unified-scheduler] Tick error")
            time.sleep(self._tick_interval)

    def _tick(self) -> None:
        now = datetime.utcnow()
        due = self.job_repo.list_due_schedules(now)
        for schedule in due:
            locked = self.job_repo.lock_schedule(
                schedule.schedule_id, now + timedelta(seconds=300),
            )
            if not locked:
                continue
            try:
                self._dispatch(schedule)
            except Exception:
                logger.exception("[unified-scheduler] Dispatch failed for %s", schedule.schedule_id)
            finally:
                next_run = now + timedelta(seconds=schedule.interval_seconds)
                self.job_repo.finish_schedule_run(schedule.schedule_id, next_run)

    def _dispatch(self, schedule: Schedule) -> None:
        if schedule.schedule_type == "sniffer_pack":
            input_data = self._build_sniffer_input(schedule.ref_id)
            if input_data is None:
                return
            job_type = "sniffer_search"
        elif schedule.schedule_type == "source_run":
            input_data = {"source_id": schedule.ref_id}
            job_type = "source_run"
        else:
            return

        job = self.job_repo.create_job(Job(
            job_id=uuid.uuid4().hex[:12],
            job_type=job_type,
            input_json=json.dumps(input_data),
        ))
        self.job_runner.run(job.job_id)
        logger.info("[unified-scheduler] Dispatched %s job %s for %s/%s",
                     job_type, job.job_id, schedule.schedule_type, schedule.ref_id)

    def _build_sniffer_input(self, pack_id: str) -> dict | None:
        pack = self.sniffer_repo.get_pack(pack_id)
        if not pack:
            return None
        q_data = json.loads(pack.query_json)
        return {
            "keyword": q_data.get("keyword", ""),
            "channels": q_data.get("channels", []),
            "time_range": q_data.get("time_range", "all"),
            "sort_by": q_data.get("sort_by", "relevance"),
            "max_results_per_channel": q_data.get("max_results_per_channel", 10),
            "pack_id": pack_id,
        }
