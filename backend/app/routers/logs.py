from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.container import AppContainer

logger = logging.getLogger("sailor")
router = APIRouter(prefix="/logs", tags=["logs"])

# 简单的内存日志队列（生产环境可用 Redis/DB）
_log_queue: list[dict[str, str]] = []
_max_queue_size = 200


def add_log(level: str, message: str) -> None:
    import datetime

    _log_queue.append(
        {
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        }
    )
    if len(_log_queue) > _max_queue_size:
        _log_queue.pop(0)



# Lazy-add handler on first emit to avoid import order issues
_log_handler_installed = False


def _install_handler() -> None:
    global _log_handler_installed
    if _log_handler_installed:
        return
    root = logging.getLogger()
    if not any(isinstance(h, LogHandler) for h in root.handlers):
        h = LogHandler()
        h.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        root.addHandler(h)
        import sys
        print(f"DEBUG: LogHandler added to root. root.handlers={len(root.handlers)}", file=sys.stderr)
    _log_handler_installed = True
    import sys
    print(f"DEBUG: _install_handler called. root handlers count={len(root.handlers)}", file=sys.stderr)


class LogHandler(logging.Handler):
    _allowed_prefixes = ("sailor", "backend", "core", "uvicorn.error")

    def emit(self, record: logging.LogRecord) -> None:
        if not any(record.name.startswith(p) for p in self._allowed_prefixes):
            return
        try:
            add_log(record.levelname, self.format(record))
        except Exception:
            return


# Install handler at import time
_root_logger = logging.getLogger()
if not any(isinstance(h, LogHandler) for h in _root_logger.handlers):
    _handler = LogHandler()
    _handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    _root_logger.addHandler(_handler)
    import sys
    print(f"DEBUG: LogHandler installed at module import. handlers={len(_root_logger.handlers)}", file=sys.stderr)
else:
    import sys
    print(f"DEBUG: LogHandler already present at module import. handlers={len(_root_logger.handlers)}", file=sys.stderr)

# Test log to verify system works
import sys
print(f"DEBUG: Logs module loaded. Queue size: {len(_log_queue)}", file=sys.stderr)


def mount_log_routes(container: AppContainer) -> APIRouter:
    # Test log to verify system works
    add_log("INFO", "[system] log route mounted - logging system active")
    import sys
    print(f"DEBUG: mount_log_routes called. Queue now has {len(_log_queue)} entries", file=sys.stderr)
    @router.get("/stream")
    async def log_stream() -> StreamingResponse:
        async def event_generator() -> AsyncGenerator[str, None]:
            import asyncio

            last_index = len(_log_queue)
            while True:
                await asyncio.sleep(2)

                while last_index < len(_log_queue):
                    log = _log_queue[last_index]
                    last_index += 1
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
        return _log_queue[-safe_limit:]

    return router
