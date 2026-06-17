"""Build a news daily-brief (themed roundup) from scraped items + the house view.

Pure-ish and deterministic: group the day's headlines by topic, pick the most
recent per theme, and compose a single-narrative summary plus a one-line
"market read" that ties the news to the latest prediction (regime/direction).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from kospi_watcher.db import models
from kospi_watcher.domain.enums import MarketDirection
from kospi_watcher.domain.news_brief import NewsBrief, NewsHeadline, NewsTheme
from kospi_watcher.domain.prediction.regime import REGIME_KO
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.time import UTC, now_utc


def _aware(dt: datetime) -> datetime:
    """Coerce a DB datetime to UTC-aware (SQLite drops tzinfo)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

_DIR_KO: dict[MarketDirection, str] = {
    MarketDirection.BULLISH: "강세",
    MarketDirection.BEARISH: "약세",
    MarketDirection.NEUTRAL: "중립",
}
_PER_THEME = 4


def _trim(text: str, limit: int = 60) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _market_read(prediction: MarketPrediction | None) -> str:
    if prediction is None:
        return "아직 오늘의 예측 리포트가 생성되지 않았다."
    return (
        f"에이전트 21인의 데스크 토의·수석 조율 결과, 시장은 "
        f"{REGIME_KO.get(prediction.regime, prediction.regime.value)} 국면"
        f"({_DIR_KO[prediction.direction]}, 확신 {prediction.confidence:.0%})으로 읽힌다 — "
        f"{prediction.headline}"
    )


def build_news_brief(
    date_kst: str,
    rows: Sequence[models.NewsItemRow],
    prediction: MarketPrediction | None,
    *,
    generated_by: str = "rule",
) -> NewsBrief:
    # Group by topic, newest first within each theme.
    by_topic: dict[str, list[models.NewsItemRow]] = {}
    for row in sorted(rows, key=lambda r: r.published_at, reverse=True):
        by_topic.setdefault(row.topic, []).append(row)

    themes = [
        NewsTheme(
            topic=topic,
            count=len(items),
            headlines=[
                NewsHeadline(
                    title=it.title,
                    source=it.source,
                    url=it.url,
                    published_at=_aware(it.published_at),
                )
                for it in items[:_PER_THEME]
            ],
        )
        for topic, items in sorted(by_topic.items(), key=lambda kv: len(kv[1]), reverse=True)
    ]

    market_read = _market_read(prediction)
    if not rows:
        summary = f"{date_kst} 수집된 뉴스가 없습니다. 뉴스 스크랩을 먼저 실행하세요. {market_read}"
    else:
        leads = [
            f"{t.topic} 부문에서는 '{_trim(t.headlines[0].title)}' 등 {t.count}건"
            for t in themes[:3]
            if t.headlines
        ]
        summary = (
            f"{date_kst} 한국 증시 관련 뉴스 {len(rows)}건을 종합했다. "
            + ("; ".join(leads) + "이(가) 주목됐다. " if leads else "")
            + market_read
        )

    return NewsBrief(
        date=date_kst,
        item_count=len(rows),
        summary=summary,
        market_read=market_read,
        themes=themes,
        generated_by=generated_by,
        created_at=now_utc(),
    )
