"""Keyless Korean-market news via the Google News RSS endpoint.

No API key; a ``User-Agent`` is sent. The provider never raises: on any network
or parse error it returns an empty list so scraping degrades safely. The client
is injectable for offline unit tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element, ParseError

import httpx
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring as safe_fromstring

from kospi_watcher.domain.time import UTC, now_utc
from kospi_watcher.infrastructure.news.base import NewsItem, make_item_id

_BASE = "https://news.google.com/rss/search"
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class GoogleNewsProvider:
    name = "google"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        user_agent: str = _DEFAULT_UA,
        timeout: float = 8.0,
        max_items: int = 15,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._ua = user_agent
        self._timeout = timeout
        self._max = max_items

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def fetch(
        self, topic: str, *, as_of: datetime | None = None
    ) -> Sequence[NewsItem]:
        try:
            client = await self._get_client()
            resp = await client.get(
                _BASE,
                params={"q": topic, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
                headers={"User-Agent": self._ua},
            )
            if resp.status_code != 200:
                return []
            return self._parse(topic, resp.content)
        except (httpx.HTTPError, ParseError, ValueError, DefusedXmlException):
            return []

    def _parse(self, topic: str, content: bytes) -> list[NewsItem]:
        root: Element = safe_fromstring(content)
        items: list[NewsItem] = []
        for el in root.findall(".//item")[: self._max]:
            title = (el.findtext("title") or "").strip()
            link = (el.findtext("link") or "").strip()
            if not title or not link:
                continue
            src_el = el.find("source")
            source = (
                src_el.text.strip()
                if src_el is not None and src_el.text
                else "Google News"
            )
            published = _parse_pubdate(el.findtext("pubDate"))
            suffix = f" - {source}"
            clean = title[: -len(suffix)] if title.endswith(suffix) else title
            items.append(
                NewsItem(
                    id=make_item_id(link, clean),
                    title=clean,
                    url=link,
                    source=source,
                    topic=topic,
                    published_at=published,
                    summary=None,
                )
            )
        return items

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


def _parse_pubdate(raw: str | None) -> datetime:
    if not raw:
        return now_utc()
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return now_utc()
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
