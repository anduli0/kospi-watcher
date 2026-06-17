"""APScheduler-based worker jobs.

In RESEARCH/mock mode these jobs only exercise the analysis agents and emit
structured logs. They never create orders.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from kospi_watcher.agent_service.prediction import PredictionService
from kospi_watcher.db.repositories import recent_headlines, save_prediction
from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.registry import get_registry
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.db import get_sessionmaker
from kospi_watcher.logging_config import get_logger
from kospi_watcher.newsfeed.service import NewsService

log = get_logger("worker")


async def heartbeat() -> None:
    log.info("worker.heartbeat", at=now_utc().isoformat())


async def mock_agent_sweep() -> None:
    registry = get_registry()
    ctx = AgentContext(as_of=now_utc(), universe=("069500", "102110"))
    runs = registry.run_all(ctx)
    succeeded = sum(1 for r in runs if r.status.value == "SUCCEEDED")
    log.info("worker.mock_agent_sweep", agents=len(runs), succeeded=succeeded)


async def scrape_news() -> None:
    """Fetch the configured news topics, store new items, prune old ones."""
    async with get_sessionmaker()() as session:
        result = await NewsService().scrape(session)
    log.info("worker.scrape_news", added=result.added, pruned=result.pruned)


async def refresh_prediction() -> None:
    """Generate and persist a fresh house prediction / daily brief (news-aware)."""
    async with get_sessionmaker()() as session:
        headlines = await recent_headlines(session, limit=8)
        prediction = await PredictionService().generate(
            ("069500", "114800", "252670"), news_headlines=headlines
        )
        await save_prediction(session, prediction)
        await session.commit()
    log.info(
        "worker.refresh_prediction",
        direction=prediction.direction.value,
        regime=prediction.regime.value,
        by=prediction.generated_by,
    )


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(heartbeat, "interval", seconds=60, id="heartbeat", replace_existing=True)
    scheduler.add_job(
        mock_agent_sweep, "interval", minutes=15, id="mock_agent_sweep", replace_existing=True
    )
    scheduler.add_job(
        scrape_news, "interval", minutes=60, id="scrape_news", replace_existing=True
    )
    scheduler.add_job(
        refresh_prediction,
        "interval",
        minutes=30,
        id="refresh_prediction",
        replace_existing=True,
    )
    return scheduler
