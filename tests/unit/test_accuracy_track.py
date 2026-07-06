"""Unit tests for prediction tracking + the auto-feedback calibration (ADR-027)."""

from __future__ import annotations

from decimal import Decimal

from kospi_watcher.domain.enums import MarketDirection
from kospi_watcher.domain.prediction.accuracy_track import build_track
from kospi_watcher.domain.time import now_utc


def _dates(n: int) -> list[str]:
    # synthetic but ordered date strings; build_track only uses them as labels
    return [f"2025-{(k // 28) % 12 + 1:02d}-{k % 28 + 1:02d}" for k in range(n)]


def _rising(n: int) -> list[Decimal]:
    return [Decimal(str(round(1000 * (1.004 ** k), 2))) for k in range(n)]


def _rise_then_fall(n: int) -> list[Decimal]:
    # A flat base, then a slow grind lower — the downtrend shape the
    # recalibrated signal (ADR-029) is designed to call: structure breaks while
    # the price stays inside the (-10%, -3%) bear band (a fast crash would land
    # in the oversold rebound zone, where the signal refuses to chase).
    out: list[Decimal] = []
    px = 1000.0
    for k in range(n):
        if k >= 150:
            px *= 0.999
        out.append(Decimal(str(round(px, 2))))
    return out


def test_build_track_shape_and_bounds() -> None:
    n = 360
    rep = build_track(_dates(n), _rising(n), as_of=now_utc())
    assert rep.points
    assert rep.horizon_days == 5
    for p in rep.points[:5]:
        assert p.predicted_dir in set(MarketDirection)
    s = rep.score
    assert 0.0 <= s.hit_rate <= 1.0
    assert 0.0 <= s.base_rate <= 1.0
    c = rep.calibration
    assert -0.08 <= c.direction_bias <= 0.08
    assert 0.0 <= c.confidence_target <= 1.0
    assert c.grade


def test_pure_uptrend_model_tracks_buyhold() -> None:
    n = 360
    rep = build_track(_dates(n), _rising(n), as_of=now_utc())
    # All bullish → the model-following curve equals buy & hold; no bear calls.
    assert rep.score.bear_samples == 0
    assert rep.score.bear_hit is None
    assert rep.score.bull_samples > 0
    assert abs(rep.score.final_model_cum_pct - rep.score.final_actual_cum_pct) < 0.5


def test_downturn_produces_bear_calls_and_divergence() -> None:
    n = 360
    rep = build_track(_dates(n), _rise_then_fall(n), as_of=now_utc())
    # The fall should trigger bear predictions and the model (going flat/short)
    # should diverge from buy & hold over the window.
    assert rep.score.bear_samples > 0
    diverged = any(
        abs(p.actual_cum_pct - p.model_cum_pct) > 1.0 for p in rep.points
    )
    assert diverged


def test_calibration_is_deterministic() -> None:
    n = 360
    a = build_track(_dates(n), _rising(n), as_of=now_utc())
    b = build_track(_dates(n), _rising(n), as_of=now_utc())
    assert a.calibration.direction_bias == b.calibration.direction_bias
    assert a.calibration.confidence_target == b.calibration.confidence_target
