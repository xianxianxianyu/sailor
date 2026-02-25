from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.container import AppContainer

logger = logging.getLogger("sailor")

import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger("sailor")

router = APIRouter(prefix="/logs", tags=["logs"])

# 简单的内存日志队列（生产环境可用 Redis）
_log_queue: list[dict] = []
_max_queue_size = 100


def add_log(level: str, message: str) -> None:
    """添加日志到队列"""
    import datetime
    _log_queue.append({
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message,
    })
    # 保持队列大小
    if len(_log_queue) > _max_queue_size:
        _log_queue.pop(0)


class LogHandler(logging.Handler):
    """自定义日志处理器，将日志发送到队列"""
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            level = record.levelname
            add_log(level, msg)
        except Exception:
            pass


# 添加日志处理器
handler = LogHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger("sailor").addHandler(handler)


def mount_log_routes(container: AppContainer) -> APIRouter:
    @router.get("/stream")
    async def log_stream() -> StreamingResponse:
        """SSE 日志流"""
        async def event_generator() -> AsyncGenerator[str, None]:
            import asyncio
            last_index = len(_log_queue)
            
            while True:
                await asyncio.sleep(2)
                
                # 发送新日志
                while last_index < len(_log_queue):
                    log = _log_queue[last_index]
                    last_index += 1
                    yield f"data: {log['time']} | {log['level']:8s} | {log['message']}\n\n"
                
                # 发送心跳
                yield f"data: : heartbeat\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    @router.get("")
    def get_recent_logs(limit: int = 50) -> list[dict]:
        """获取最近日志"""
        return _log_queue[-limit:]

    return router
