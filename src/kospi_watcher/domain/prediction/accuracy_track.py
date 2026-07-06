"""Prediction-vs-actual tracking, scoring, and the auto-feedback calibration
(ADR-027).

The prediction is deterministic, so for every past day we can *replay* what the
model's primary directional signal (``trend_core``) would have called, then
compare it to the realized forward move. This module builds:

* a **time series** of two equity curves — 실제(지수 매수보유) vs 모델(예측 방향
  추종) — for an at-a-glance "did the prediction track reality" chart,
* a **scorecard** (directional hit rate vs base rate, by-direction, cumulative),
* and a bounded **Calibration** (a direction bias + a confidence scale) derived
  from that scoring, which the synthesizer applies to *future* predictions —
  closing the self-improvement loop.

Pure & deterministic; ratios are ``float`` (not money), prices stay ``Decimal``.
No look-ahead: each day's signal uses only closes up to that day.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.enums import MarketDirection
from kospi_watcher.domain.prediction.trend_signal import TREND_WARMUP, trend_core

_WARMUP = TREND_WARMUP  # trend_core needs its 200-day structure SMA
_WINDOW = 250  # chart window (~1 year of trading days, to span regimes)
_H = 5  # scoring horizon (D5, matches the prediction horizon)


class TrackPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str  # KST YYYY-MM-DD
    actual_cum_pct: float  # 지수 매수보유 누적수익 %
    model_cum_pct: float  # 모델 예측방향 추종 누적수익 %
    predicted_dir: MarketDirection
    hit: bool | None  # vs forward-H realized move (None if not yet realized / neutral)


class AccuracyScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    samples: int
    hit_rate: float = Field(ge=0.0, le=1.0)
    base_rate: float = Field(ge=0.0, le=1.0)
    skill: float
    bull_samples: int
    bear_samples: int
    bull_hit: float | None = Field(default=None, ge=0.0, le=1.0)  # None when no calls
    bear_hit: float | None = Field(default=None, ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    final_actual_cum_pct: float
    final_model_cum_pct: float


class Calibration(BaseModel):
    """The auto-feedback adjustment applied to future predictions."""

    model_config = ConfigDict(extra="forbid")

    direction_bias: float  # added to the house score (toward the realized drift)
    confidence_target: float  # the realized directional hit rate the confidence
    #                           should be calibrated toward (0 = no history)
    grade: str  # honest letter grade
    basis: str  # Korean explanation of what was learned


class AccuracyTrackReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: AwareDatetime
    symbol: str
    source: str  # "yahoo" | "mock"
    horizon_days: int
    window_days: int
    points: list[TrackPoint]
    score: AccuracyScore
    calibration: Calibration
    interpretation: str


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def build_track(
    dates: Sequence[str],
    closes: Sequence[Decimal],
    *,
    as_of: AwareDatetime,
    symbol: str = "KOSPI",
    source: str = "yahoo",
) -> AccuracyTrackReport:
    n = len(closes)
    start = max(_WARMUP, n - _WINDOW)

    points: list[TrackPoint] = []
    actual_cum = 1.0
    model_cum = 1.0
    hits = directional = 0
    bull_hits = bull_n = bear_hits = bear_n = 0
    up = total_fwd = 0

    for i in range(start, n - 1):
        d, _, _, _ = trend_core(closes, i)
        daily = float(closes[i + 1] / closes[i] - Decimal("1"))
        actual_cum *= 1.0 + daily
        model_cum *= 1.0 + d * daily  # d in {-1,0,1}; flat = cash

        hit: bool | None = None
        if i + _H < n:
            fwd = float(closes[i + _H] / closes[i] - Decimal("1"))
            total_fwd += 1
            if fwd > 0:
                up += 1
            if d != 0:
                directional += 1
                won = (d > 0 and fwd > 0) or (d < 0 and fwd < 0)
                hit = won
                if won:
                    hits += 1
                if d > 0:
                    bull_n += 1
                    bull_hits += int(won)
                else:
                    bear_n += 1
                    bear_hits += int(won)

        points.append(
            TrackPoint(
                date=dates[i] if i < len(dates) else str(i),
                actual_cum_pct=round((actual_cum - 1.0) * 100, 2),
                model_cum_pct=round((model_cum - 1.0) * 100, 2),
                predicted_dir=_dir(d),
                hit=hit,
            )
        )

    score = _score(
        hits, directional, up, total_fwd, bull_hits, bull_n, bear_hits, bear_n,
        actual_cum, model_cum, len(points),
    )
    up_frac = up / total_fwd if total_fwd else 0.5
    calibration = _calibrate(score, up_frac)
    return AccuracyTrackReport(
        as_of=as_of,
        symbol=symbol,
        source=source,
        horizon_days=_H,
        window_days=len(points),
        points=points,
        score=score,
        calibration=calibration,
        interpretation=_interpret(score, calibration),
    )


def _dir(d: int) -> MarketDirection:
    return (
        MarketDirection.BULLISH if d > 0
        else MarketDirection.BEARISH if d < 0
        else MarketDirection.NEUTRAL
    )


def _score(
    hits: int, directional: int, up: int, total_fwd: int,
    bull_hits: int, bull_n: int, bear_hits: int, bear_n: int,
    actual_cum: float, model_cum: float, n_points: int,
) -> AccuracyScore:
    hit_rate = hits / directional if directional else 0.0
    base_up = up / total_fwd if total_fwd else 0.5
    base_rate = max(base_up, 1.0 - base_up)
    return AccuracyScore(
        samples=directional,
        hit_rate=round(hit_rate, 4),
        base_rate=round(base_rate, 4),
        skill=round(hit_rate - base_rate, 4),
        bull_samples=bull_n,
        bear_samples=bear_n,
        bull_hit=round(bull_hits / bull_n, 4) if bull_n else None,
        bear_hit=round(bear_hits / bear_n, 4) if bear_n else None,
        coverage=round(directional / n_points, 4) if n_points else 0.0,
        final_actual_cum_pct=round((actual_cum - 1.0) * 100, 2),
        final_model_cum_pct=round((model_cum - 1.0) * 100, 2),
    )


def _calibrate(score: AccuracyScore, up_frac: float) -> Calibration:
    # Persistent drift sign from the realized up-frequency: lean the prediction
    # into the side the market has actually been trending.
    drift_sign = 1 if up_frac > 0.5 else -1
    underperf = max(0.0, score.base_rate - score.hit_rate)
    direction_bias = _clamp(drift_sign * (0.5 * underperf + 0.03), -0.08, 0.08)

    # The well-calibrated confidence for a clear directional call is the realized
    # hit rate: if the model is directionally right ~70% of the time, a clear call
    # deserves ~70% confidence (not 50%). The synthesizer anchors toward this.
    confidence_target = round(score.hit_rate, 3) if score.samples >= 20 else 0.0

    if score.skill >= 0.02:
        grade = "B+ (기저율 상회)"
    elif score.skill >= -0.02:
        grade = "B (기저율 수준)"
    else:
        grade = "C (기저율 미달)"

    bias_ko = (
        "상승" if direction_bias > 0.005 else "하락" if direction_bias < -0.005 else "중립"
    )
    basis = (
        f"최근 {score.samples}회 채점: 방향 적중률 {score.hit_rate:.0%}"
        f"(기저율 {score.base_rate:.0%}). 지속 추세에 정합하도록 "
        f"방향 보정 {direction_bias:+.3f}({bias_ko} 쪽), 확신도를 실현 적중률 "
        f"{confidence_target:.0%}에 정합(과신/과소 교정)하도록 다음 예측에 자동 반영."
    )
    return Calibration(
        direction_bias=round(direction_bias, 4),
        confidence_target=confidence_target,
        grade=grade,
        basis=basis,
    )


def _interpret(score: AccuracyScore, cal: Calibration) -> str:
    bull = f"{score.bull_hit:.0%}" if score.bull_hit is not None else "N/A"
    bear = f"{score.bear_hit:.0%}" if score.bear_hit is not None else "N/A(예측 없음)"
    return (
        f"기간 누적: 실제(매수보유) {score.final_actual_cum_pct:+.1f}% vs "
        f"모델(예측 추종) {score.final_model_cum_pct:+.1f}%. "
        f"방향 적중률 {score.hit_rate:.0%}(기저율 {score.base_rate:.0%}, "
        f"스킬 {score.skill * 100:+.1f}%p) · 등급 {cal.grade}. "
        f"상승예측 적중 {bull}({score.bull_samples}회) / 하락예측 적중 {bear}. "
        f"이 채점 결과로 도출한 보정을 다음 예측에 자동 반영해 정확도를 개선한다."
    )
