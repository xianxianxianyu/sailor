"""SnifferToolModule — per-channel concurrent search with budget control."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass, field

from core.models import JobBudget, SniffQuery, SniffResult
from core.sniffer.channel_registry import ChannelRegistry
from core.storage.sniffer_repository import SnifferRepository

logger = logging.getLogger(__name__)


@dataclass
class WorkerResults:
    results: list[SniffResult] = field(default_factory=list)
    channels_succeeded: list[str] = field(default_factory=list)
    channels_failed: list[str] = field(default_factory=list)


def _dedup_by_url(results: list[SniffResult]) -> list[SniffResult]:
    seen: set[str] = set()
    deduped: list[SniffResult] = []
    for r in results:
        if r.url not in seen:
            seen.add(r.url)
            deduped.append(r)
    return deduped


class SnifferToolModule:
    """Executes per-channel search with tool-call tracking via RunContext."""

    def __init__(self, channel_registry: ChannelRegistry, sniffer_repo: SnifferRepository) -> None:
        self.channel_registry = channel_registry
        self.sniffer_repo = sniffer_repo

    def search_channels(self, query: SniffQuery, ctx, budget: JobBudget | None = None) -> WorkerResults:
        """Execute search per channel, each recorded as an independent tool call."""
        budget = budget or JobBudget()
        channels = query.channels or list(self.channel_registry._adapters.keys())
        adapters = [(cid, self.channel_registry.get(cid)) for cid in channels]
        adapters = [(cid, a) for cid, a in adapters if a is not None]

        if not adapters:
            return WorkerResults()

        per_channel_timeout = budget.deadline_ms / 1000  # seconds

        succeeded: list[str] = []
        failed: list[str] = []
        all_results: list[SniffResult] = []

        def _search_one(channel_id: str, adapter):
            return channel_id, adapter.search(query)

        with ThreadPoolExecutor(max_workers=min(len(adapters), budget.max_workers)) as pool:
            futures = {pool.submit(_search_one, cid, a): cid for cid, a in adapters}
            try:
                for future in as_completed(futures, timeout=per_channel_timeout):
                    cid = futures[future]
                    try:
                        _, results = future.result()
                        # Wrap each channel search through ctx.call_tool for policy consistency
                        ctx.call_tool(
                            f"search_channel:{cid}",
                            {"keyword": query.keyword, "channel": cid, "time_range": query.time_range},
                            lambda _req, _r=results: _r,
                        )
                        succeeded.append(cid)
                        all_results.extend(results)
                    except PermissionError:
                        # PolicyGate denied — mark as failed
                        failed.append(cid)
                        logger.warning("[sniffer] Policy denied search on channel %s", cid)
                    except Exception:
                        failed.append(cid)
            except TimeoutError:
                # Mark all un-finished channels as failed
                for future, cid in futures.items():
                    if not future.done():
                        failed.append(cid)
                        future.cancel()
                logger.warning("[sniffer] Timeout waiting for channels, %d timed out", len(failed))

        deduped = _dedup_by_url(all_results)
        self.sniffer_repo.save_results(deduped)
        return WorkerResults(results=deduped, channels_succeeded=succeeded, channels_failed=failed)
