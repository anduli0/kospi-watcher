"""Scrape news for the configured topics, store new items, and prune old ones.

Retention is enforced on every scrape: items older than ``news_retention_days``
are deleted, so the feed never accumulates stale history (ADR-018).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.config import get_settings
from kospi_watcher.db import repositories
from kospi_watcher.domain.news_brief import NewsBrief
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.time import now_utc, to_kst
from kospi_watcher.infrastructure.news import NewsItem, NewsProvider, get_news_provider
from kospi_watcher.newsfeed.brief_builder import build_news_brief


@dataclass(frozen=True)
class ScrapeResult:
    fetched: int
    added: int
    pruned: int
    topics: list[str]


class NewsService:
    def __init__(self, provider: NewsProvider | None = None) -> None:
        self._provider = provider or get_news_provider()

    async def scrape(
        self,
        session: AsyncSession,
        *,
        topics: list[str] | None = None,
        retention_days: int | None = None,
    ) -> ScrapeResult:
        settings = get_settings()
        topics = topics or settings.news_topics
        retention = retention_days if retention_days is not None else settings.news_retention_days

        deduped: dict[str, NewsItem] = {}
        for topic in topics:
            for item in await self._provider.fetch(topic):
                deduped.setdefault(item.id, item)
        items = list(deduped.values())

        added = await repositories.upsert_news(session, items)
        cutoff = now_utc() - timedelta(days=retention)
        pruned = await repositories.prune_news(session, older_than=cutoff)
        await session.commit()
        return ScrapeResult(fetched=len(items), added=added, pruned=pruned, topics=topics)

    async def generate_daily_brief(
        self, session: AsyncSession, *, date_kst: str | None = None
    ) -> NewsBrief:
        """Build and persist the news daily brief for a KST day (today by default),
        tying the day's headlines to the latest prediction's house view."""
        date_kst = date_kst or to_kst(now_utc()).date().isoformat()
        rows = await repositories.list_news(session, date_kst=date_kst, limit=200)

        pred_row = await repositories.get_latest_prediction(session)
        prediction = (
            MarketPrediction.model_validate(pred_row.payload) if pred_row is not None else None
        )

        brief = build_news_brief(date_kst, rows, prediction)
        await repositories.save_daily_brief(session, brief)
        await session.commit()
        return brief
