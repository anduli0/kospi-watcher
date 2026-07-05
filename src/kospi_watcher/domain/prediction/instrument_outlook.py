"""Per-instrument position verdict + short/mid/long price outlook (ADR-023).

Given the house view (direction / confidence / regime) from the prediction
engine, this turns each rung of the long/inverse/leveraged ladder
(069500 / 122630 / 114800 / 252670) into:

* a **position verdict** — 매수(BUY) / 중립(HOLD) / 매도(SELL) — reusing the same
  deterministic ``stance_for`` the prediction already uses, and
* a **short / mid / long price outlook** — a signed expected return and a
  low/base/high target *range*, derived from the house's expected index drift
  scaled by the instrument's exposure sign and leverage, **minus** the
  volatility-decay drag that daily-rebalanced leveraged/inverse ETFs suffer over
  longer horizons, with a Korean rationale per horizon.

Pure & deterministic (no I/O, no ``float`` for money, ADR-008). The price targets
are an explainable **model-based scenario projection**, not a guarantee — labelled
as such in the report disclaimer.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.enums import (
    InstrumentKind,
    MarketDirection,
    MarketRegime,
    StanceLabel,
)
from kospi_watcher.domain.money import DecimalNoFloat, to_decimal
from kospi_watcher.domain.prediction.instruments import PREDICTION_UNIVERSE, stance_for
from kospi_watcher.domain.prediction.monetary_policy import MonetaryPolicySignal
from kospi_watcher.domain.prediction.trend_signal import TrendSignal


class OutlookHorizon(StrEnum):
    SHORT = "SHORT"  # 단기 (1주~1개월)
    MID = "MID"  # 중기 (1~3개월)
    LONG = "LONG"  # 장기 (6~12개월)


class PositionVerdict(StrEnum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


# --- schemas ---------------------------------------------------------------


class HorizonProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon: OutlookHorizon
    label: str
    direction: MarketDirection
    expected_return_pct: Decimal  # signed % for THIS instrument
    target_low: DecimalNoFloat | None
    target_base: DecimalNoFloat | None
    target_high: DecimalNoFloat | None
    rationale: str


class InstrumentOutlook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    kind: InstrumentKind
    current_price: DecimalNoFloat | None
    price_source: str  # "yahoo" | "mock" | "none"
    verdict: PositionVerdict
    verdict_label: str  # "매수" | "중립" | "비중축소" | "회피"
    stance_label: StanceLabel
    conviction: float = Field(ge=0.0, le=1.0)
    summary: str
    risk_note: str | None
    projections: list[HorizonProjection]


class InstrumentAnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: AwareDatetime
    subject: str
    direction: MarketDirection
    confidence: float = Field(ge=0.0, le=1.0)
    regime: MarketRegime
    generated_by: str  # "mock" | "llm" — provenance of the house view
    house_summary: str
    monetary_policy: MonetaryPolicySignal | None
    trend_signal: TrendSignal | None
    instruments: list[InstrumentOutlook]
    price_source: str  # dominant ("yahoo" | "mock" | "none")
    disclaimer: str


# --- model constants -------------------------------------------------------

_HORIZON_LABEL: dict[OutlookHorizon, str] = {
    OutlookHorizon.SHORT: "단기 (1주~1개월)",
    OutlookHorizon.MID: "중기 (1~3개월)",
    OutlookHorizon.LONG: "장기 (6~12개월)",
}
# Index expected drift at full conviction (|s|=1), per horizon, in %.
_INDEX_DRIFT: dict[OutlookHorizon, Decimal] = {
    OutlookHorizon.SHORT: Decimal("3.0"),
    OutlookHorizon.MID: Decimal("7.0"),
    OutlookHorizon.LONG: Decimal("14.0"),
}
# Index 1x volatility half-band per horizon, in % (neutral regime).
_INDEX_BAND: dict[OutlookHorizon, Decimal] = {
    OutlookHorizon.SHORT: Decimal("2.5"),
    OutlookHorizon.MID: Decimal("5.5"),
    OutlookHorizon.LONG: Decimal("10.0"),
}
# Base volatility-decay unit per horizon (%), scaled by rebalance intensity & vol.
_DECAY_UNIT: dict[OutlookHorizon, Decimal] = {
    OutlookHorizon.SHORT: Decimal("0.3"),
    OutlookHorizon.MID: Decimal("1.6"),
    OutlookHorizon.LONG: Decimal("5.0"),
}
# How much a regime bias compounds with horizon.
_TILT_WEIGHT: dict[OutlookHorizon, Decimal] = {
    OutlookHorizon.SHORT: Decimal("0.4"),
    OutlookHorizon.MID: Decimal("1.0"),
    OutlookHorizon.LONG: Decimal("2.0"),
}
# Regime → (additive index drift tilt %, volatility multiplier).
_REGIME: dict[MarketRegime, tuple[Decimal, Decimal]] = {
    MarketRegime.RISK_ON_STRONG: (Decimal("1.0"), Decimal("1.00")),
    MarketRegime.RISK_ON_FRAGILE: (Decimal("0.3"), Decimal("1.15")),
    MarketRegime.LIQUIDITY_RALLY: (Decimal("0.8"), Decimal("1.05")),
    MarketRegime.EARNINGS_RALLY: (Decimal("0.8"), Decimal("0.95")),
    MarketRegime.SIDEWAYS_LOW_VOL: (Decimal("0.0"), Decimal("0.70")),
    MarketRegime.SIDEWAYS_HIGH_VOL: (Decimal("0.0"), Decimal("1.35")),
    MarketRegime.RISK_OFF: (Decimal("-1.0"), Decimal("1.30")),
    MarketRegime.CRISIS: (Decimal("-2.5"), Decimal("1.80")),
    MarketRegime.DATA_UNCERTAIN: (Decimal("0.0"), Decimal("1.25")),
}
# Exposure sign (+long / -inverse), leverage, and daily-rebalance decay intensity.
_EXPOSURE: dict[InstrumentKind, int] = {
    InstrumentKind.LONG_1X: 1,
    InstrumentKind.LONG_2X: 1,
    InstrumentKind.INVERSE_1X: -1,
    InstrumentKind.INVERSE_2X: -1,
}
_LEVERAGE: dict[InstrumentKind, Decimal] = {
    InstrumentKind.LONG_1X: Decimal("1"),
    InstrumentKind.LONG_2X: Decimal("2"),
    InstrumentKind.INVERSE_1X: Decimal("1"),
    InstrumentKind.INVERSE_2X: Decimal("2"),
}
_REBAL: dict[InstrumentKind, Decimal] = {
    InstrumentKind.LONG_1X: Decimal("0"),  # plain long: no structural decay
    InstrumentKind.LONG_2X: Decimal("2"),
    InstrumentKind.INVERSE_1X: Decimal("1"),  # futures-based: mild decay
    InstrumentKind.INVERSE_2X: Decimal("3"),  # 곱버스: heaviest decay
}
_DIR_SIGN: dict[MarketDirection, int] = {
    MarketDirection.BULLISH: 1,
    MarketDirection.BEARISH: -1,
    MarketDirection.NEUTRAL: 0,
}

_DIRECTION_KO = {
    MarketDirection.BULLISH: "강세",
    MarketDirection.BEARISH: "약세",
    MarketDirection.NEUTRAL: "중립",
}
_REGIME_KO = {
    MarketRegime.RISK_ON_STRONG: "강한 위험선호",
    MarketRegime.RISK_ON_FRAGILE: "취약한 위험선호",
    MarketRegime.LIQUIDITY_RALLY: "유동성 랠리",
    MarketRegime.EARNINGS_RALLY: "실적 랠리",
    MarketRegime.SIDEWAYS_LOW_VOL: "저변동성 횡보",
    MarketRegime.SIDEWAYS_HIGH_VOL: "고변동성 횡보",
    MarketRegime.RISK_OFF: "위험회피",
    MarketRegime.CRISIS: "위기",
    MarketRegime.DATA_UNCERTAIN: "데이터 불확실",
}
_VERDICT: dict[StanceLabel, tuple[PositionVerdict, str]] = {
    StanceLabel.OVERWEIGHT: (PositionVerdict.BUY, "매수"),
    StanceLabel.NEUTRAL: (PositionVerdict.HOLD, "중립"),
    StanceLabel.UNDERWEIGHT: (PositionVerdict.SELL, "비중축소"),
    StanceLabel.AVOID: (PositionVerdict.SELL, "회피"),
}

_DISCLAIMER = (
    "목표가는 하우스 방향·확신도·국면을 종목의 노출/레버리지/데케이로 투영한 "
    "모델 기반 시나리오이며, 확정된 예측이나 투자자문이 아닙니다. 레버리지·인버스"
    "(곱버스)는 일일 리밸런싱 데케이와 원금 손실 위험이 큽니다."
)

_ONE = Decimal("1")
_HUNDRED = Decimal("100")


def _q_price(value: Decimal) -> Decimal:
    return value.quantize(_ONE, rounding=ROUND_HALF_UP)


def _q_pct(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _signed(value: Decimal) -> str:
    return f"{'+' if value > 0 else ''}{value}"


def _project_one(
    kind: InstrumentKind,
    current_price: Decimal | None,
    horizon: OutlookHorizon,
    s: Decimal,
    regime: MarketRegime,
) -> HorizonProjection:
    tilt, vol_mult = _REGIME[regime]
    exposure = _EXPOSURE[kind]
    leverage = _LEVERAGE[kind]
    rebal = _REBAL[kind]

    idx_move = _q_pct(s * _INDEX_DRIFT[horizon] + tilt * _TILT_WEIGHT[horizon])
    inst_raw = _q_pct(idx_move * leverage * Decimal(exposure))
    decay = _q_pct(_DECAY_UNIT[horizon] * rebal * vol_mult)  # always a cost
    inst_move = _q_pct(inst_raw - decay)
    band = _q_pct(_INDEX_BAND[horizon] * leverage * vol_mult)

    if inst_move > Decimal("0.7"):
        hdir = MarketDirection.BULLISH
    elif inst_move < Decimal("-0.7"):
        hdir = MarketDirection.BEARISH
    else:
        hdir = MarketDirection.NEUTRAL

    label = _HORIZON_LABEL[horizon]
    exp_ko = "롱" if exposure > 0 else "인버스(숏)"
    lev_ko = "2배 " if leverage == 2 else ""

    if current_price is None or current_price <= 0:
        rationale = (
            f"{label}: 지수 {_signed(idx_move)}% 가정 → {lev_ko}{exp_ko} "
            f"{_signed(inst_move)}% 내외. 시세 없음으로 목표가 산출 보류."
        )
        return HorizonProjection(
            horizon=horizon,
            label=label,
            direction=hdir,
            expected_return_pct=inst_move,
            target_low=None,
            target_base=None,
            target_high=None,
            rationale=rationale,
        )

    base = _q_price(current_price * (_ONE + inst_move / _HUNDRED))
    low = _q_price(current_price * (_ONE + (inst_move - band) / _HUNDRED))
    high = _q_price(current_price * (_ONE + (inst_move + band) / _HUNDRED))
    floor = _q_price(current_price * Decimal("0.05"))
    low = max(low, floor)

    decay_note = (
        f", 일일 리밸런싱 데케이 -{decay}% 반영" if rebal > 0 and decay > 0 else ""
    )
    rationale = (
        f"지수 {_signed(idx_move)}% 가정 · {lev_ko}{exp_ko} {_signed(inst_raw)}%"
        f"{decay_note} → 기대수익 {_signed(inst_move)}%."
    )
    return HorizonProjection(
        horizon=horizon,
        label=label,
        direction=hdir,
        expected_return_pct=inst_move,
        target_low=low,
        target_base=base,
        target_high=high,
        rationale=rationale,
    )


def build_outlook(
    symbol: str,
    name: str,
    kind: InstrumentKind,
    current_price: Decimal | None,
    price_source: str,
    direction: MarketDirection,
    confidence: float,
    regime: MarketRegime,
) -> InstrumentOutlook:
    """One instrument's verdict + 3-horizon price outlook."""
    stance = stance_for(kind, direction, confidence, regime)
    verdict, verdict_label = _VERDICT[stance.label]
    s = to_decimal(str(_DIR_SIGN[direction])) * to_decimal(str(confidence))
    projections = [
        _project_one(kind, current_price, h, s, regime) for h in OutlookHorizon
    ]
    summary = f"{verdict_label} — {stance.rationale}"
    return InstrumentOutlook(
        symbol=symbol,
        name=name,
        kind=kind,
        current_price=current_price,
        price_source=price_source,
        verdict=verdict,
        verdict_label=verdict_label,
        stance_label=stance.label,
        conviction=confidence,
        summary=summary,
        risk_note=stance.risk_note,
        projections=projections,
    )


def build_report(
    direction: MarketDirection,
    confidence: float,
    regime: MarketRegime,
    generated_by: str,
    prices: dict[str, tuple[Decimal | None, str]],
    as_of: AwareDatetime,
    *,
    subject: str = "코스피200 지수 방향",
    monetary_policy: MonetaryPolicySignal | None = None,
    trend_signal: TrendSignal | None = None,
) -> InstrumentAnalysisReport:
    """Build the full ladder report from the house view + live prices.

    ``prices`` maps internal symbol → (price | None, source). Iterates the
    canonical long/inverse/leveraged ladder (``PREDICTION_UNIVERSE``).
    """
    instruments: list[InstrumentOutlook] = []
    sources: list[str] = []
    for inst in PREDICTION_UNIVERSE:
        price, source = prices.get(inst.symbol, (None, "none"))
        sources.append(source)
        instruments.append(
            build_outlook(
                inst.symbol,
                inst.name,
                inst.kind,
                price,
                source,
                direction,
                confidence,
                regime,
            )
        )
    live = [s for s in sources if s == "yahoo"]
    dominant = "yahoo" if len(live) >= len(sources) - len(live) and live else (
        "mock" if any(s == "mock" for s in sources) else "none"
    )
    house_summary = (
        f"코스피200 {_DIRECTION_KO[direction]} 전망(확신도 "
        f"{round(confidence * 100)}%), {_REGIME_KO[regime]} 국면."
    )
    return InstrumentAnalysisReport(
        as_of=as_of,
        subject=subject,
        direction=direction,
        confidence=confidence,
        regime=regime,
        generated_by=generated_by,
        house_summary=house_summary,
        monetary_policy=monetary_policy,
        trend_signal=trend_signal,
        instruments=instruments,
        price_source=dominant,
        disclaimer=_DISCLAIMER,
    )
