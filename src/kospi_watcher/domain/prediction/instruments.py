"""The prediction instrument ladder and per-instrument stance logic.

Covers the full long/short leverage ladder so a *bearish* house view yields an
actionable **inverse / leveraged-inverse (곱버스)** stance, not just "avoid long":

    069500  KODEX 200            LONG_1X
    122630  KODEX 레버리지         LONG_2X
    114800  KODEX 인버스          INVERSE_1X
    252670  KODEX 200선물인버스2X  INVERSE_2X  ("곱버스")

``stance_for`` maps (house direction, confidence, regime) to a stance per
instrument, accounting for leverage and volatility-decay risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from kospi_watcher.domain.enums import (
    InstrumentKind,
    MarketDirection,
    MarketRegime,
    StanceLabel,
)


@dataclass(frozen=True)
class PredictionInstrument:
    symbol: str
    name: str
    kind: InstrumentKind


PREDICTION_UNIVERSE: tuple[PredictionInstrument, ...] = (
    PredictionInstrument("069500", "KODEX 200", InstrumentKind.LONG_1X),
    PredictionInstrument("122630", "KODEX 레버리지", InstrumentKind.LONG_2X),
    PredictionInstrument("114800", "KODEX 인버스", InstrumentKind.INVERSE_1X),
    PredictionInstrument("252670", "KODEX 200선물인버스2X", InstrumentKind.INVERSE_2X),
)

# Exposure sign (+long / -inverse) and leverage magnitude per kind.
_EXPOSURE: dict[InstrumentKind, int] = {
    InstrumentKind.LONG_1X: +1,
    InstrumentKind.LONG_2X: +1,
    InstrumentKind.INVERSE_1X: -1,
    InstrumentKind.INVERSE_2X: -1,
}
_LEVERAGE: dict[InstrumentKind, int] = {
    InstrumentKind.LONG_1X: 1,
    InstrumentKind.LONG_2X: 2,
    InstrumentKind.INVERSE_1X: 1,
    InstrumentKind.INVERSE_2X: 2,
}
_DIR_SIGN: dict[MarketDirection, int] = {
    MarketDirection.BULLISH: +1,
    MarketDirection.BEARISH: -1,
    MarketDirection.NEUTRAL: 0,
}

# Regimes where leveraged products suffer outsized volatility-decay risk.
_HIGH_VOL_REGIMES = frozenset(
    {MarketRegime.SIDEWAYS_HIGH_VOL, MarketRegime.CRISIS, MarketRegime.DATA_UNCERTAIN}
)

_LEVERAGE_RISK_NOTE = (
    "레버리지·일일 리밸런싱에 따른 변동성 손실(데케이) 위험 — 장기 보유 부적합."
)

_HIGH, _MED = 0.55, 0.35


@dataclass(frozen=True)
class Stance:
    label: StanceLabel
    rationale: str
    risk_note: str | None = None


def stance_for(
    kind: InstrumentKind,
    direction: MarketDirection,
    confidence: float,
    regime: MarketRegime,
) -> Stance:
    """Return the house stance on ``kind`` given the market view."""
    leverage = _LEVERAGE[kind]
    is_inverse = _EXPOSURE[kind] < 0
    risk = _LEVERAGE_RISK_NOTE if leverage == 2 else None
    alignment = _EXPOSURE[kind] * _DIR_SIGN[direction]  # +1 favorable, -1 against, 0 neutral
    band = "high" if confidence >= _HIGH else "med" if confidence >= _MED else "low"
    high_vol = regime in _HIGH_VOL_REGIMES
    side_ko = "인버스(숏)" if is_inverse else "롱"

    if direction is MarketDirection.NEUTRAL:
        if leverage == 2:
            return Stance(
                StanceLabel.UNDERWEIGHT,
                f"방향성 부재 — {side_ko} 레버리지는 횡보 데케이로 비중축소.",
                risk,
            )
        return Stance(StanceLabel.NEUTRAL, f"방향성 부재 — {side_ko} 중립.")

    if alignment > 0:  # instrument agrees with the house view
        if leverage == 1:
            label = StanceLabel.OVERWEIGHT if band in ("high", "med") else StanceLabel.NEUTRAL
            return Stance(label, f"전망과 정합 — {side_ko} {_ko(label)}.")
        # leveraged, aligned
        if regime is MarketRegime.CRISIS:
            return Stance(StanceLabel.AVOID, f"위기 국면 — {side_ko} 레버리지 회피.", risk)
        if band == "high" and not high_vol:
            label = StanceLabel.OVERWEIGHT
        elif band == "high":
            label = StanceLabel.NEUTRAL  # high conviction but choppy: decay risk
        elif band == "med":
            label = StanceLabel.NEUTRAL
        else:
            label = StanceLabel.UNDERWEIGHT
        return Stance(label, f"전망과 정합하나 레버리지 — {side_ko} {_ko(label)}.", risk)

    # alignment < 0: instrument fights the house view
    if leverage == 1:
        label = (
            StanceLabel.AVOID
            if band == "high"
            else StanceLabel.UNDERWEIGHT
            if band == "med"
            else StanceLabel.NEUTRAL
        )
    else:
        label = StanceLabel.AVOID if band in ("high", "med") else StanceLabel.UNDERWEIGHT
    return Stance(label, f"전망과 역행 — {side_ko} {_ko(label)}.", risk)


def _ko(label: StanceLabel) -> str:
    return {
        StanceLabel.OVERWEIGHT: "비중확대",
        StanceLabel.NEUTRAL: "중립",
        StanceLabel.UNDERWEIGHT: "비중축소",
        StanceLabel.AVOID: "회피",
    }[label]
