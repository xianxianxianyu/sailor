from __future__ import annotations

import datetime
import logging
import threading
from collections import deque
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.container import AppContainer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["logs"])

# Monotonically increasing sequence counter + deque for bounded log storage
_seq_lock = threading.Lock()
_seq_counter: int = 0
_max_queue_size = 200
_log_deque: deque[dict] = deque(maxlen=_max_queue_size)


def add_log(level: str, message: str) -> None:
    """Append a log entry to the in-memory deque with a monotonic seq number."""
    global _seq_counter
    with _seq_lock:
        _seq_counter += 1
        seq = _seq_counter
    _log_deque.append(
        {
            "seq": seq,
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        }
    )


class LogHandler(logging.Handler):
    """Bridge: standard logging -> in-memory deque for frontend SSE."""

    _allowed_prefixes = ("backend", "core", "uvicorn.error")

    def emit(self, record: logging.LogRecord) -> None:
        if not any(record.name.startswith(p) for p in self._allowed_prefixes):
            return
        try:
            add_log(record.levelname, self.format(record))
        except Exception:
            return


def mount_log_routes(container: AppContainer) -> APIRouter:
    @router.get("/stream")
    async def log_stream() -> StreamingResponse:
        async def event_generator() -> AsyncGenerator[str, None]:
            import asyncio

            last_seq = _seq_counter
            while True:
                await asyncio.sleep(2)

                # Scan deque for entries newer than last_seq
                for log in list(_log_deque):
                    if log["seq"] > last_seq:
                        last_seq = log["seq"]
                        yield f"data: {log['time']} | {log['level']:8s} | {log['message']}\n\n"

                yield "data: : heartbeat\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    @router.get("")
    def get_recent_logs(limit: int = 50) -> list[dict[str, str]]:
        safe_limit = max(1, min(limit, 500))
        recent = list(_log_deque)[-safe_limit:]
        # Exclude internal 'seq' field from API response
        return [{k: v for k, v in entry.items() if k != "seq"} for entry in recent]

    return router
