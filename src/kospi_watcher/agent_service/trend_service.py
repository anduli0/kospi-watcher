"""Provides the latest price-trend signal that anchors the prediction (ADR-025/029).

Fetches ~2y of daily closes (the recalibrated signal needs the 200-day structure
SMA + headroom) and builds the deterministic :class:`TrendSignal`. Cached for a
TTL; never fails (labelled offline series on fetch failure)."""

from __future__ import annotations

import random
import time
from decimal import Decimal

from kospi_watcher.domain.prediction.trend_signal import TrendSignal, build_trend_signal
from kospi_watcher.infrastructure.marketdata.history import fetch_daily_closes


def _mock_series(n: int = 420) -> list[Decimal]:
    rng = random.Random(20260618)  # noqa: S311 (non-crypto, deterministic offline)
    px = 2500.0
    out: list[Decimal] = []
    for _ in range(n):
        px *= 1.0 + 0.0004 + (rng.random() - 0.5) * 0.018
        out.append(Decimal(str(round(px, 2))))
    return out


class TrendService:
    def __init__(self, *, ttl_seconds: int = 900) -> None:
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, TrendSignal]] = {}

    async def latest(self, symbol: str = "KOSPI") -> TrendSignal:
        now = time.monotonic()
        cached = self._cache.get(symbol)
        if cached is not None and cached[0] > now:
            return cached[1]
        closes = await fetch_daily_closes(symbol, rng="2y")
        if len(closes) >= 260:
            source = "yahoo"
        else:
            closes = _mock_series()
            source = "mock"
        signal = build_trend_signal(closes, source=source)
        self._cache[symbol] = (now + self._ttl, signal)
        return signal


_service: TrendService | None = None


def get_trend_service() -> TrendService:
    global _service
    if _service is None:
        _service = TrendService()
    return _service
