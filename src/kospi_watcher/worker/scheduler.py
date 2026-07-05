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
from kospi_watcher.db import repositories
from kospi_watcher.domain.time import now_utc, to_kst
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


async def ensure_daily_briefing() -> None:
    """Catch-up safety net so the daily brief is *guaranteed once a day*.

    The 08:00 cron only fires if the worker happens to be alive at exactly that
    moment — a PC that was off at 08:00 (and logged in at, say, 09:11), a resume
    from sleep, or a crash-restart would otherwise silently skip the whole day.
    This job (run on startup and every 30 min) checks whether today's (KST) news
    brief already exists; if not, and it's already past the scheduled briefing
    time, it runs the full morning pipeline now. Idempotent — once today's brief
    exists it returns immediately, so it never double-sends on a normal day."""
    settings = get_settings()
    now_kst = to_kst(now_utc())
    today_kst = now_kst.date().isoformat()
    async with get_sessionmaker()() as session:
        existing = await repositories.get_daily_brief(session, today_kst)
    if existing is not None:
        return  # already produced today (by the cron, a manual run, or an earlier catch-up)
    scheduled = now_kst.replace(
        hour=settings.morning_briefing_hour,
        minute=settings.morning_briefing_minute,
        second=0,
        microsecond=0,
    )
    if now_kst < scheduled:
        return  # before today's scheduled time — let the 08:00 cron handle it
    log.info("worker.ensure_daily_briefing.catch_up", date=today_kst)
    await morning_briefing()


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
        # If the loop was briefly busy/suspended at 08:00, still run (up to 1h late)
        # rather than silently skip; coalesce collapses any pile-up to one run.
        misfire_grace_time=3600,
        coalesce=True,
    )
    # Catch-up safety net: runs immediately on start, then every 30 min. Guarantees
    # today's brief even if the worker missed the exact 08:00 cron (PC off, sleep,
    # crash-restart). Idempotent once today's brief exists.
    scheduler.add_job(
        ensure_daily_briefing,
        "interval",
        minutes=30,
        id="ensure_daily_briefing",
        replace_existing=True,
        next_run_time=now_utc(),
        misfire_grace_time=600,
        coalesce=True,
    )
    return scheduler
