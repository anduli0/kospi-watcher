"""Builds the individual-stock recommendation report (ADR-026).

Fetches each universe name's daily closes in parallel (keyless Yahoo), computes
real momentum/trend features, then combines the site's house view (latest
prediction → direction/regime/BOK), the live sector board, and recent news
catalysts, and runs the deterministic :func:`recommend`. Cached for a TTL; never
fails (names that don't fetch simply score on theme/policy with no momentum)."""

from __future__ import annotations

import time
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.agent_service.backtest_service import _mock_series
from kospi_watcher.db import repositories
from kospi_watcher.domain.enums import MarketDirection, MarketRegime
from kospi_watcher.domain.prediction.monetary_policy import PolicyStance
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.stocks import (
    STOCK_UNIVERSE,
    HouseContext,
    StockRecommendationReport,
    StockSignal,
    recommend,
)
from kospi_watcher.domain.stocks.universe import StockMeta
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.marketdata.analysis import get_market_analysis_service
from kospi_watcher.infrastructure.marketdata.history import fetch_daily_closes


def _mom(closes: list[Decimal], n: int) -> Decimal | None:
    if len(closes) <= n:
        return None
    return (closes[-1] / closes[-(n + 1)] - Decimal("1")) * Decimal("100")


def _above_ma(closes: list[Decimal], n: int) -> bool:
    if len(closes) < n:
        return False
    return closes[-1] > sum(closes[-n:], Decimal("0")) / Decimal(n)


def _stretch_pct(closes: list[Decimal], n: int = 120) -> Decimal | None:
    """Price vs its n-day SMA, in % — an overextension / 과열 proxy."""
    if len(closes) < n:
        return None
    sma = sum(closes[-n:], Decimal("0")) / Decimal(n)
    if sma == 0:
        return None
    return (closes[-1] / sma - Decimal("1")) * Decimal("100")


class StockRecommendationService:
    def __init__(self, *, ttl_seconds: int = 1800) -> None:
        self._ttl = ttl_seconds
        self._cache: tuple[float, StockRecommendationReport] | None = None

    async def build(self, session: AsyncSession) -> StockRecommendationReport:
        now = time.monotonic()
        if self._cache is not None and self._cache[0] > now:
            return self._cache[1]
        report = await self._build_fresh(session)
        self._cache = (now + self._ttl, report)
        return report

    async def _build_fresh(self, session: AsyncSession) -> StockRecommendationReport:
        ctx = await self._house_context(session)
        sector_moves = await self._sector_moves()
        headlines = await repositories.recent_headlines(session, limit=40)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
        ) as client:
            series = await self._fetch_all(client)

        live = sum(1 for c in series.values() if len(c) >= 130)
        offline = live < len(STOCK_UNIVERSE) // 2
        signals: list[StockSignal] = []
        for meta in STOCK_UNIVERSE:
            closes = series.get(meta.code) or []
            if len(closes) < 130 and offline:
                closes = _mock_series(160)  # labelled offline fallback
            signals.append(self._signal(meta, closes, sector_moves, headlines))

        return recommend(
            signals,
            ctx,
            as_of=now_utc(),
            price_source="mock" if offline else "yahoo",
        )

    async def _fetch_all(self, client: httpx.AsyncClient) -> dict[str, list[Decimal]]:
        import asyncio

        # The universe is now broad (~300 names), so cap concurrency to stay a
        # good citizen with Yahoo (avoid bursts → rate limits). Each fetch never
        # raises; a name that fails simply scores without momentum.
        sem = asyncio.Semaphore(12)

        async def one(meta: StockMeta) -> tuple[str, list[Decimal]]:
            async with sem:
                closes = await fetch_daily_closes(meta.yahoo, rng="1y", client=client)
            return meta.code, closes

        results = await asyncio.gather(*(one(m) for m in STOCK_UNIVERSE))
        return dict(results)

    def _signal(
        self,
        meta: StockMeta,
        closes: list[Decimal],
        sector_moves: dict[str, Decimal],
        headlines: list[str],
    ) -> StockSignal:
        news_hit = next(
            (h for h in headlines if any(a in h for a in meta.aliases)), None
        )
        return StockSignal(
            meta=meta,
            price=closes[-1] if closes else None,
            mom20=_mom(closes, 20),
            mom60=_mom(closes, 60),
            mom120=_mom(closes, 120),
            above_ma20=_above_ma(closes, 20),
            above_ma60=_above_ma(closes, 60),
            above_ma120=_above_ma(closes, 120),
            stretch_pct=_stretch_pct(closes),
            sector_change_pct=sector_moves.get(meta.sector_key),
            news_hit=news_hit,
        )

    async def _sector_moves(self) -> dict[str, Decimal]:
        try:
            board = await get_market_analysis_service().build()
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return {}
        return {s.key: s.change_pct for s in board.sectors}

    async def _house_context(self, session: AsyncSession) -> HouseContext:
        row = await repositories.get_latest_prediction(session)
        if row is None:
            return HouseContext(
                MarketDirection.NEUTRAL, MarketRegime.SIDEWAYS_LOW_VOL, PolicyStance.NEUTRAL
            )
        pred = MarketPrediction.model_validate(row.payload)
        stance = pred.monetary_policy.stance if pred.monetary_policy else PolicyStance.NEUTRAL
        return HouseContext(pred.direction, pred.regime, stance)


_service: StockRecommendationService | None = None


def get_stock_recommendation_service() -> StockRecommendationService:
    global _service
    if _service is None:
        _service = StockRecommendationService()
    return _service
