"""News providers: Google RSS parsing (offline) + mock."""

from __future__ import annotations

import httpx

from kospi_watcher.infrastructure.news.google_rss import GoogleNewsProvider
from kospi_watcher.infrastructure.news.mock import MockNewsProvider

_SAMPLE_RSS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<rss version="2.0"><channel><item>'
    "<title>코스피 강보합 - 연합뉴스</title>"
    "<link>https://news.google.com/rss/articles/abc123</link>"
    "<pubDate>Wed, 17 Jun 2026 00:42:49 GMT</pubDate>"
    '<source url="https://yna.co.kr">연합뉴스</source>'
    "</item></channel></rss>"
).encode()


async def test_google_rss_parses_offline() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=_SAMPLE_RSS))
    provider = GoogleNewsProvider(client=httpx.AsyncClient(transport=transport))
    items = await provider.fetch("코스피")
    assert len(items) == 1
    item = items[0]
    assert item.title == "코스피 강보합"  # trailing " - source" stripped
    assert item.source == "연합뉴스"
    assert item.topic == "코스피"
    assert item.url.startswith("https://news.google.com/")
    assert item.published_at.tzinfo is not None
    await provider.aclose()


async def test_google_rss_degrades_on_error() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(503, text="down"))
    provider = GoogleNewsProvider(client=httpx.AsyncClient(transport=transport))
    assert await provider.fetch("코스피") == []
    await provider.aclose()


async def test_mock_news_provider_is_deterministic() -> None:
    items = await MockNewsProvider().fetch("코스피")
    assert len(items) == 4
    assert all(i.source == "MOCK" for i in items)
    assert len({i.id for i in items}) == 4
