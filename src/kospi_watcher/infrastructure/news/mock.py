"""Deterministic offline news provider (tests / no-network)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.news.base import NewsItem, make_item_id

_MOCK_HEADLINES = [
    "[MOCK] 코스피, 외국인 순매수에 강보합",
    "[MOCK] 반도체 수출 회복 기대에 IT주 강세",
    "[MOCK] 원/달러 환율 변동성 확대",
    "[MOCK] 기관 차익실현에 장중 등락",
]


class MockNewsProvider:
    name = "mock"

    async def fetch(
        self, topic: str, *, as_of: datetime | None = None
    ) -> Sequence[NewsItem]:
        base = as_of or now_utc()
        items: list[NewsItem] = []
        for i, head in enumerate(_MOCK_HEADLINES):
            url = f"https://example.test/mock/{topic}/{i}"
            items.append(
                NewsItem(
                    id=make_item_id(url, head),
                    title=f"{head} ({topic})",
                    url=url,
                    source="MOCK",
                    topic=topic,
                    published_at=base - timedelta(hours=i + 1),
                    summary=None,
                )
            )
        return items
