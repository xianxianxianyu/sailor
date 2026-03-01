"""Centralized logging configuration for Sailor."""

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for the entire application. Call once at startup."""
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
