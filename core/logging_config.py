"""Centralized logging configuration for Sailor."""

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


def setup_logging(level: int | None = None) -> None:
    """Configure logging for the entire application. Call once at startup."""
    if level is None:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to avoid duplicates
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root.addHandler(console)

    # Bridge handler: logging -> in-memory queue (for frontend SSE)
    from backend.app.routers.logs import LogHandler

    bridge = LogHandler()
    bridge.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root.addHandler(bridge)

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "feedparser", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
