from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from core.models import SnifferPack

logger = logging.getLogger(__name__)

# Simple cron-like intervals: "every_1h", "every_6h", "every_12h", "every_24h"
_INTERVAL_MAP = {
    "every_1h": 3600,
    "every_6h": 6 * 3600,
    "every_12h": 12 * 3600,
    "every_24h": 24 * 3600,
}


def _parse_interval(cron: str | None) -> int | None:
    if not cron:
        return None
    return _INTERVAL_MAP.get(cron)


def _next_run(interval_sec: int) -> datetime:
    return datetime.utcnow() + timedelta(seconds=interval_sec)


class SnifferScheduler:
    """Simple threading.Timer-based scheduler for sniffer packs."""

    def __init__(self, pack_manager, sniffer_repo) -> None:
        self._pack_manager = pack_manager
        self._repo = sniffer_repo
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._stopped = False

    def start(self) -> None:
        packs = self._repo.list_scheduled_packs()
        for pack in packs:
            self._schedule(pack)
        logger.info("[scheduler] Started with %d scheduled packs", len(packs))

    def stop(self) -> None:
        self._stopped = True
        with self._lock:
            for t in self._timers.values():
                t.cancel()
            self._timers.clear()

    def reschedule(self, pack: SnifferPack) -> None:
        with self._lock:
            old = self._timers.pop(pack.pack_id, None)
            if old:
                old.cancel()
        if pack.schedule_cron:
            self._schedule(pack)

    def _schedule(self, pack: SnifferPack) -> None:
        interval = _parse_interval(pack.schedule_cron)
        if not interval:
            return
        delay = interval
        if pack.next_run_at:
            remaining = (pack.next_run_at - datetime.utcnow()).total_seconds()
            if remaining > 0:
                delay = remaining
        timer = threading.Timer(delay, self._run, args=(pack.pack_id, interval))
        timer.daemon = True
        with self._lock:
            self._timers[pack.pack_id] = timer
        timer.start()

    def _run(self, pack_id: str, interval: int) -> None:
        if self._stopped:
            return
        try:
            self._pack_manager.run_pack(pack_id)
            now = datetime.utcnow()
            nxt = _next_run(interval)
            self._repo.update_pack_last_run(pack_id, now.isoformat(), nxt.isoformat())
            logger.info("[scheduler] Ran pack %s, next at %s", pack_id, nxt.isoformat())
        except Exception as exc:
            logger.warning("[scheduler] Pack %s run failed: %s", pack_id, exc)
        # Re-schedule
        pack = self._repo.get_pack(pack_id)
        if pack and pack.schedule_cron and not self._stopped:
            self._schedule(pack)
