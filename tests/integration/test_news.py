"""News scraping service: upsert, dedup, retention prune (DB-backed)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.db import repositories
from kospi_watcher.infrastructure.news.mock import MockNewsProvider
from kospi_watcher.newsfeed.service import NewsService


async def test_scrape_inserts_and_dedups(session: AsyncSession) -> None:
    svc = NewsService(provider=MockNewsProvider())
    first = await svc.scrape(session, topics=["코스피"], retention_days=14)
    assert first.fetched == 4 and first.added == 4

    rows = await repositories.list_news(session)
    assert len(rows) == 4

    # Re-scraping the same topic adds nothing (dedup by stable id).
    second = await svc.scrape(session, topics=["코스피"], retention_days=14)
    assert second.added == 0
    assert len(await repositories.list_news(session)) == 4


async def test_retention_prunes_old(session: AsyncSession) -> None:
    svc = NewsService(provider=MockNewsProvider())
    await svc.scrape(session, topics=["코스피"], retention_days=14)
    # retention_days=0 -> everything older than 'now' is pruned.
    result = await svc.scrape(session, topics=["코스피"], retention_days=0)
    assert result.pruned >= 4
    assert await repositories.list_news(session) == []


async def test_news_dates_grouping(session: AsyncSession) -> None:
    await NewsService(provider=MockNewsProvider()).scrape(
        session, topics=["코스피"], retention_days=14
    )
    dates = await repositories.news_dates(session)
    assert dates  # at least one (date, count) pair
    assert sum(c for _, c in dates) == 4
