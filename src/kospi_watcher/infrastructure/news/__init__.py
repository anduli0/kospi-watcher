"""News providers (keyless Google News RSS / deterministic mock)."""

from __future__ import annotations

from kospi_watcher.infrastructure.news.base import NewsItem, NewsProvider, make_item_id
from kospi_watcher.infrastructure.news.factory import (
    get_news_provider,
    reset_news_provider,
)
from kospi_watcher.infrastructure.news.google_rss import GoogleNewsProvider
from kospi_watcher.infrastructure.news.mock import MockNewsProvider

__all__ = [
    "GoogleNewsProvider",
    "MockNewsProvider",
    "NewsItem",
    "NewsProvider",
    "get_news_provider",
    "make_item_id",
    "reset_news_provider",
]
