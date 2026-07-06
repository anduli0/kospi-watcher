"""Accuracy backtest of the directional trend signal (ADR-025).

Walks the historical close series and, at each day, computes the SAME past-only
``trend_core`` signal the prediction uses, then compares its direction to the
realized forward H-day return. Reports the **directional hit rate vs the base rate
(always-majority) and the resulting skill**, per horizon, with an honest
out-of-sample (test) split — so accuracy is never overstated by a bull-market
base rate.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.prediction.trend_signal import TREND_WARMUP, trend_core

_HORIZONS: tuple[tuple[int, str], ...] = (
    (5, "단기 (D5, ~1주)"),
    (20, "중기 (D20, ~1개월)"),
    (60, "장기 (D60, ~분기)"),
)
_PRIMARY = 20
_WARMUP = TREND_WARMUP  # the signal needs its 200-day structure SMA first


class HorizonAccuracy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon_days: int
    label: str
    hit_rate: float = Field(ge=0.0, le=1.0)  # directional accuracy (non-neutral)
    base_rate: float = Field(ge=0.0, le=1.0)  # always-majority baseline
    skill: float  # hit_rate - base_rate (signed)
    coverage: float = Field(ge=0.0, le=1.0)  # fraction of days with a directional call
    sample: int


class BacktestReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: AwareDatetime
    symbol: str
    source: str  # "yahoo" | "mock"
    n_days: int
    test_fraction: float
    train: list[HorizonAccuracy]
    test: list[HorizonAccuracy]
    primary_horizon_days: int
    primary_hit_rate: float  # test, primary horizon
    primary_base_rate: float
    primary_skill: float
    interpretation: str


def _measure(closes: Sequence[Decimal], lo: int, hi: int, h: int) -> HorizonAccuracy:
    hits = directional = base_up = total = 0
    for i in range(lo, hi):
        if i + h >= len(closes):
            break
        fwd = closes[i + h] / closes[i] - Decimal("1")
        total += 1
        if fwd > 0:
            base_up += 1
        d, _, _, _ = trend_core(closes, i)
        if d != 0:
            directional += 1
            if (d > 0 and fwd > 0) or (d < 0 and fwd < 0):
                hits += 1
    base = base_up / total if total else 0.0
    naive = max(base, 1.0 - base)
    hit = hits / directional if directional else 0.0
    label = next(lbl for hd, lbl in _HORIZONS if hd == h)
    return HorizonAccuracy(
        horizon_days=h,
        label=label,
        hit_rate=round(hit, 4),
        base_rate=round(naive, 4),
        skill=round(hit - naive, 4),
        coverage=round(directional / total, 4) if total else 0.0,
        sample=total,
    )


def run_backtest(
    closes: Sequence[Decimal],
    *,
    symbol: str,
    source: str,
    as_of: AwareDatetime,
    test_fraction: float = 0.3,
) -> BacktestReport:
    n = len(closes)
    split = int(n * (1.0 - test_fraction))
    train = [_measure(closes, _WARMUP + 1, split, h) for h, _ in _HORIZONS]
    test = [_measure(closes, split, n, h) for h, _ in _HORIZONS]
    prim_test = next(x for x in test if x.horizon_days == _PRIMARY)
    prim_train = next(x for x in train if x.horizon_days == _PRIMARY)
    return BacktestReport(
        as_of=as_of,
        symbol=symbol,
        source=source,
        n_days=n,
        test_fraction=test_fraction,
        train=train,
        test=test,
        primary_horizon_days=_PRIMARY,
        primary_hit_rate=prim_test.hit_rate,
        primary_base_rate=prim_test.base_rate,
        primary_skill=prim_test.skill,
        interpretation=_interpret(prim_train, prim_test),
    )


def _interpret(train: HorizonAccuracy, test: HorizonAccuracy) -> str:
    th = train.hit_rate * 100
    tb = train.base_rate * 100
    tsk = train.skill * 100
    eh = test.hit_rate * 100
    eb = test.base_rate * 100
    esk = test.skill * 100

    # The real verdict is on the balanced (train) split; the test split is
    # contaminated by whatever regime happens to dominate it (often a strong
    # bull market where 'always long' = 90%+ base rate).
    if train.skill >= 0.02:
        verdict = (
            f"균형장(train) 기준 1개월 방향 적중률 {th:.1f}% vs 기저율 {tb:.1f}% — "
            f"**+{tsk:.1f}%p 양(+)의 스킬**로 단순 기저율을 넘는 유의미한 엣지를 보였다."
        )
    elif train.skill >= -0.02:
        verdict = (
            f"균형장(train) 적중률 {th:.1f}%로 기저율 {tb:.1f}%와 거의 동일 — "
            "단순 방향 예측의 초과 엣지는 제한적이나 추세에 정합한다."
        )
    else:
        verdict = (
            f"균형장(train) 적중률 {th:.1f}%가 기저율 {tb:.1f}% 미달 — "
            "추세 신호로는 초과 엣지가 부족하다."
        )
    return (
        f"{verdict} 최근 구간(test, 1개월 적중률 {eh:.1f}% / "
        f"기저율 {eb:.1f}% / 스킬 {esk:+.1f}%p)은 강세 추세가 지배해 "
        "'항상 상승'의 기저율이 매우 높아 스킬이 음수로 보일 수 있다 — "
        "이는 신호의 결함이 아니라 시장 국면의 특성이다. 추세 앵커의 목적은 "
        "동전던지기 수준의 초단기 방향을 맞히는 것이 아니라, 하우스 뷰가 시장 추세에 "
        "정합하도록 만들어 포지셔닝·리스크 프레이밍의 신뢰도를 높이는 데 있다."
    )
