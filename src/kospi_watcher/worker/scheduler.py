"""APScheduler-based worker jobs.

In RESEARCH/mock mode these jobs only exercise the analysis agents and emit
structured logs. They never create orders.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.registry import get_registry
from kospi_watcher.domain.time import now_utc
from kospi_watcher.logging_config import get_logger

log = get_logger("worker")


async def heartbeat() -> None:
    log.info("worker.heartbeat", at=now_utc().isoformat())


async def mock_agent_sweep() -> None:
    registry = get_registry()
    ctx = AgentContext(as_of=now_utc(), universe=("069500", "102110"))
    runs = registry.run_all(ctx)
    succeeded = sum(1 for r in runs if r.status.value == "SUCCEEDED")
    log.info("worker.mock_agent_sweep", agents=len(runs), succeeded=succeeded)


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(heartbeat, "interval", seconds=60, id="heartbeat", replace_existing=True)
    scheduler.add_job(
        mock_agent_sweep, "interval", minutes=15, id="mock_agent_sweep", replace_existing=True
    )
    return scheduler
