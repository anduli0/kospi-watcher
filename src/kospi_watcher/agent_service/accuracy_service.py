"""Builds the prediction-tracking report and the auto-feedback calibration
(ADR-027).

Fetches dated daily closes (keyless Yahoo), replays the model over history via
:func:`build_track`, and caches the result. Exposes both the full report (for the
chart/scorecard) and just the :class:`Calibration` (for the synthesizer's feedback
loop). Never fails — falls back to a labelled offline series."""

from __future__ import annotations

import time
from datetime import timedelta
from decimal import Decimal

from kospi_watcher.agent_service.backtest_service import _mock_series
from kospi_watcher.domain.prediction.accuracy_track import (
    AccuracyTrackReport,
    Calibration,
    build_track,
)
from kospi_watcher.domain.time import now_utc, to_kst
from kospi_watcher.infrastructure.marketdata.history import fetch_daily_dated

_NEUTRAL_CALIBRATION = Calibration(
    direction_bias=0.0,
    confidence_target=0.0,
    grade="N/A",
    basis="채점 이력 부족 — 보정 미적용.",
)


def _mock_dated(n: int = 500) -> tuple[list[str], list[Decimal]]:
    closes = _mock_series(n)
    base = to_kst(now_utc()).date()
    dates = [(base - timedelta(days=(n - 1 - k))).isoformat() for k in range(n)]
    return dates, closes


class PredictionAccuracyService:
    def __init__(self, *, ttl_seconds: int = 1800) -> None:
        self._ttl = ttl_seconds
        self._cache: tuple[float, AccuracyTrackReport] | None = None

    async def report(self) -> AccuracyTrackReport:
        now = time.monotonic()
        if self._cache is not None and self._cache[0] > now:
            return self._cache[1]
        dated = await fetch_daily_dated("KOSPI", rng="2y")
        if len(dated) >= 200:
            dates = [d for d, _ in dated]
            closes = [c for _, c in dated]
            source = "yahoo"
        else:
            dates, closes = _mock_dated()
            source = "mock"
        report = build_track(dates, closes, as_of=now_utc(), symbol="KOSPI", source=source)
        self._cache = (now + self._ttl, report)
        return report

    async def calibration(self) -> Calibration:
        try:
            return (await self.report()).calibration
        except Exception:  # never let calibration break a prediction
            return _NEUTRAL_CALIBRATION


_service: PredictionAccuracyService | None = None


def get_accuracy_service() -> PredictionAccuracyService:
    global _service
    if _service is None:
        _service = PredictionAccuracyService()
    return _service
