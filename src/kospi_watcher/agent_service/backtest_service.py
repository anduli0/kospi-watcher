"""Runs the accuracy backtest over live (Yahoo) history (ADR-025).

Fetches the daily close series and runs the pure :func:`run_backtest`. Caches the
report for a TTL (the series barely changes intraday). Falls back to a clearly
labelled deterministic offline series if history is unavailable, so the endpoint
never fails.
"""

from __future__ import annotations

import random
import time
from decimal import Decimal

from kospi_watcher.domain.prediction.backtest import BacktestReport, run_backtest
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.marketdata.history import fetch_daily_closes


def _mock_series(n: int = 1220) -> list[Decimal]:
    """Deterministic mildly-trending noisy series for offline fallback."""
    rng = random.Random(20260618)  # noqa: S311 (non-crypto, deterministic offline)
    px = 2500.0
    out: list[Decimal] = []
    for _ in range(n):
        px *= 1.0 + 0.0003 + (rng.random() - 0.5) * 0.02
        out.append(Decimal(str(round(px, 2))))
    return out


class BacktestService:
    def __init__(self, *, ttl_seconds: int = 900) -> None:
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, BacktestReport]] = {}

    async def report(self, symbol: str = "KOSPI") -> BacktestReport:
        now = time.monotonic()
        cached = self._cache.get(symbol)
        if cached is not None and cached[0] > now:
            return cached[1]
        # 10y spans multiple regimes (2020 crash, 2022 bear, box + bull years),
        # so the train/test verdict is regime-diverse. (range=max is broken on
        # Yahoo for these indices — it returns ~1.5y; "10y" works.)
        closes = await fetch_daily_closes(symbol, rng="10y")
        if len(closes) >= 200:
            source = "yahoo"
        else:  # offline / blocked — labelled deterministic fallback
            closes = _mock_series()
            source = "mock"
        report = run_backtest(closes, symbol=symbol, source=source, as_of=now_utc())
        self._cache[symbol] = (now + self._ttl, report)
        return report


_service: BacktestService | None = None


def get_backtest_service() -> BacktestService:
    global _service
    if _service is None:
        _service = BacktestService()
    return _service
