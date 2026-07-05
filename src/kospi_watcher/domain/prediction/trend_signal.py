"""Real, data-driven price-trend signal — the directional anchor (ADR-025).

The mock agents are date-independent, so the un-anchored house view has no link to
the actual market. This module derives a **deterministic directional signal from
past-only price features** (price vs its 100-day SMA, gated by 60-day momentum),
which the prediction injects into the FLOW_TECH desk so the house view tracks the
real trend. The *same* core function is measured by the backtest (``backtest.py``),
so the reported accuracy is the accuracy of what actually drives the prediction.

Anchoring to the trend raises directional accuracy toward its realistic ceiling
(the market base rate); it does not claim to beat that base rate (see the backtest
interpretation). No look-ahead: every feature uses only closes up to the decision
index.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from kospi_watcher.domain.agents.schemas import AgentFinding, Evidence
from kospi_watcher.domain.enums import Impact, MarketDirection, SourceType
from kospi_watcher.domain.money import DecimalNoFloat
from kospi_watcher.domain.time import now_utc

_MA = 100  # trend SMA window (trading days)
_MOM = 60  # momentum lookback (trading days)
_HUG_BAND = Decimal("0.005")  # |price/SMA-1| below this = no trend (hugging the MA)

# The FLOW_TECH agent whose finding carries the price-trend anchor.
TREND_AGENT = "Breadth and Technical Agent"


class TrendSignal(BaseModel):
    """The price-trend directional anchor for the prediction."""

    model_config = ConfigDict(extra="forbid")

    direction: MarketDirection
    strength: float = Field(ge=0.0, le=1.0)
    price: DecimalNoFloat | None
    sma100: DecimalNoFloat | None
    mom60_pct: Decimal | None  # signed 60-day momentum, %
    note: str
    source: str  # "yahoo" | "mock" | "none"


def trend_core(
    closes: Sequence[Decimal], i: int
) -> tuple[int, float, Decimal | None, Decimal | None]:
    """Past-only trend at index ``i`` (inclusive). Returns (dir{-1,0,1}, strength,
    sma100, mom60). Abstains (0) when price hugs the MA or momentum disagrees."""
    if i < _MA:
        return 0, 0.0, None, None
    price = closes[i]
    sma = sum(closes[i - _MA + 1 : i + 1], Decimal("0")) / Decimal(_MA)
    mom = (closes[i] / closes[i - _MOM] - Decimal("1")) if i >= _MOM else None
    if sma == 0:
        return 0, 0.0, sma, mom
    dist = price / sma - Decimal("1")  # signed distance from the trend line
    ma_pos = 1 if dist > 0 else -1
    if abs(dist) < _HUG_BAND:
        return 0, 0.1, sma, mom  # price on the MA → no clear trend
    if mom is not None:
        mom_dir = 1 if mom > 0 else -1
        if ma_pos != mom_dir:
            return 0, 0.2, sma, mom  # trend vs momentum conflict → abstain
    strength = float(abs(dist)) * 8.0 + (float(abs(mom)) * 3.0 if mom is not None else 0.0)
    return ma_pos, min(1.0, strength), sma, mom


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def build_trend_signal(closes: Sequence[Decimal], *, source: str) -> TrendSignal:
    """The latest trend signal from a close series (oldest→newest)."""
    if not closes:
        return TrendSignal(
            direction=MarketDirection.NEUTRAL, strength=0.0, price=None, sma100=None,
            mom60_pct=None, note="시세 이력 없음 — 추세 판단 보류.", source="none",
        )
    i = len(closes) - 1
    d, strength, sma, mom = trend_core(closes, i)
    direction = (
        MarketDirection.BULLISH if d > 0
        else MarketDirection.BEARISH if d < 0
        else MarketDirection.NEUTRAL
    )
    mom_pct = _q2(mom * Decimal("100")) if mom is not None else None
    if direction is MarketDirection.BULLISH:
        note = f"주가가 100일선 위·60일 모멘텀 {mom_pct}%로 상승추세 (강도 {strength:.0%})."
    elif direction is MarketDirection.BEARISH:
        note = f"주가가 100일선 아래·모멘텀 {mom_pct}%로 하락추세 (강도 {strength:.0%})."
    else:
        note = "주가가 100일선 부근이거나 추세·모멘텀이 상충해 방향 불명확 (추세 중립)."
    return TrendSignal(
        direction=direction,
        strength=round(strength, 3),
        price=_q2(closes[i]),
        sma100=_q2(sma) if sma is not None else None,
        mom60_pct=mom_pct,
        note=note,
        source=source,
    )


def apply_trend_to_findings(
    findings: Sequence[AgentFinding], signal: TrendSignal
) -> list[AgentFinding]:
    """Override the FLOW_TECH technical agent's finding with the price-trend anchor.

    A NEUTRAL/None trend is a no-op (backward compatible). The override makes the
    desk-level signal — and thus the visible deliberation — track the real trend."""
    if signal.direction is MarketDirection.NEUTRAL:
        return list(findings)
    impact = Impact.HIGH if signal.strength >= 0.4 else Impact.MEDIUM
    confidence = min(0.9, 0.5 + signal.strength * 0.4)
    evidence = Evidence(
        source_id=f"trend-{signal.source}",
        source_type=SourceType.PRICE_DATA,
        title="100일 추세선·60일 모멘텀",
        published_at=now_utc(),
        available_at=now_utc(),
        claim=signal.note,
    )
    out: list[AgentFinding] = []
    for f in findings:
        if f.agent_name == TREND_AGENT:
            out.append(
                f.model_copy(
                    update={
                        "direction": signal.direction,
                        "impact": impact,
                        "confidence": round(confidence, 2),
                        "thesis": signal.note,
                        "evidence": [evidence],
                        "affected_symbols": ["069500"],
                        "invalidation_conditions": ["100일선 하향 이탈", "60일 모멘텀 부호 전환"],
                    }
                )
            )
        else:
            out.append(f)
    return out
