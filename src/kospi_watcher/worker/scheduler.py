"""APScheduler-based worker jobs.

The headline job is the daily **morning briefing** (08:00 Asia/Seoul by default):
it scrapes news, regenerates the prediction report and the news daily brief, and
pushes both to Telegram — no manual command needed. News is also refreshed hourly
so the web feed stays current. In RESEARCH/mock mode no orders are ever created.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from kospi_watcher.briefing.service import run_morning_briefing
from kospi_watcher.config import get_settings
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.db import get_sessionmaker
from kospi_watcher.logging_config import get_logger
from kospi_watcher.newsfeed.service import NewsService

log = get_logger("worker")


async def heartbeat() -> None:
    log.info("worker.heartbeat", at=now_utc().isoformat())


async def scrape_news() -> None:
    """Fetch the configured news topics, store new items, prune old ones."""
    async with get_sessionmaker()() as session:
        result = await NewsService().scrape(session)
    log.info("worker.scrape_news", added=result.added, pruned=result.pruned)


async def morning_briefing() -> None:
    """Daily: scrape → predict → news brief → Telegram (08:00 Asia/Seoul)."""
    async with get_sessionmaker()() as session:
        result = await run_morning_briefing(session)
    log.info(
        "worker.morning_briefing",
        news_added=result.news_added,
        direction=result.prediction_direction,
        brief_items=result.brief_items,
        telegram_report=result.telegram_report,
        telegram_enabled=result.telegram_enabled,
    )


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(heartbeat, "interval", seconds=60, id="heartbeat", replace_existing=True)
    scheduler.add_job(
        scrape_news, "interval", minutes=60, id="scrape_news", replace_existing=True
    )
    scheduler.add_job(
        morning_briefing,
        CronTrigger(
            hour=settings.morning_briefing_hour,
            minute=settings.morning_briefing_minute,
            timezone="Asia/Seoul",
        ),
        id="morning_briefing",
        replace_existing=True,
    )
    return scheduler
