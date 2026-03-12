"""HTTP middleware for Sailor backend."""

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Logs HTTP requests with method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next):
        # Skip logging for health check and log streaming endpoints
        if request.url.path in ("/healthz", "/logs/stream"):
            return await call_next(request)

        start_time = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "%s %s - %s - %dms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response
