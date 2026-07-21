"""Provides the latest semiconductor mega-cap cycle signal (ADR-031).

Fetches ~6 months of daily closes for Samsung Electronics (005930) and SK hynix
(000660) — the KOSPI leadership — and builds the deterministic
:class:`SemiconductorSignal`. Cached for a TTL; never fails (an offline/empty
series yields a NEUTRAL no-op signal that leaves the prediction unchanged)."""

from __future__ import annotations

import time

from kospi_watcher.config import get_settings
from kospi_watcher.domain.prediction.semiconductor import (
    SemiconductorSignal,
    build_signal,
)
from kospi_watcher.infrastructure.marketdata.history import fetch_daily_closes


class SemiconductorService:
    def __init__(self, *, ttl_seconds: int = 900) -> None:
        self._ttl = ttl_seconds
        self._cache: tuple[float, SemiconductorSignal] | None = None

    async def latest(self) -> SemiconductorSignal:
        now = time.monotonic()
        if self._cache is not None and self._cache[0] > now:
            return self._cache[1]
        settings = get_settings()
        samsung = await fetch_daily_closes("005930", rng="6mo")
        hynix = await fetch_daily_closes("000660", rng="6mo")
        signal = build_signal(
            stance_override=settings.semiconductor_cycle_stance,
            samsung_closes=samsung,
            hynix_closes=hynix,
        )
        self._cache = (now + self._ttl, signal)
        return signal


_service: SemiconductorService | None = None


def get_semiconductor_service() -> SemiconductorService:
    global _service
    if _service is None:
        _service = SemiconductorService()
    return _service
