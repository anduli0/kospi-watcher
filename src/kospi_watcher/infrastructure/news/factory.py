"""Process-wide news-provider selection (``NEWS_PROVIDER``: google | mock)."""

from __future__ import annotations

from kospi_watcher.config import get_settings
from kospi_watcher.infrastructure.news.base import NewsProvider
from kospi_watcher.infrastructure.news.google_rss import GoogleNewsProvider
from kospi_watcher.infrastructure.news.mock import MockNewsProvider

_provider: NewsProvider | None = None


def get_news_provider() -> NewsProvider:
    global _provider
    if _provider is None:
        _provider = (
            GoogleNewsProvider()
            if get_settings().news_provider == "google"
            else MockNewsProvider()
        )
    return _provider


async def reset_news_provider() -> None:
    global _provider
    if isinstance(_provider, GoogleNewsProvider):
        await _provider.aclose()
    _provider = None
