"""Real, data-driven price-trend signal — the directional anchor (ADR-025/029).

The house view must track the actual market, so a **deterministic, past-only
price signal** is injected into the FLOW_TECH desk and tilts the Chief score.
The *same* core function is measured by the backtest (``backtest.py``) and the
accuracy tracker (``accuracy_track.py``), so the reported accuracy is the
accuracy of what actually drives the prediction.

ADR-029 recalibrated the rule on 29 years of KOSPI history (walk-forward
selection, held-out recent-3y + KOSDAQ validation, bear-window gates):

* **Bullish by default** — the index drifts up, so the anchor stays long unless
  a downtrend is *confirmed*.
* **Bearish only under strict confirmation**: price more than 3% below the
  100-day average AND negative 60-day momentum AND the 50-day average below the
  200-day average (trend structure broken).
* **No bear-chasing when deeply oversold**: more than 10% below the 100-day
  average is the rebound-variance zone — the anchor returns to a *weak* default
  long instead of calling further downside.

vs the previous symmetric rule this raised the recent-3y D5 hit 53.4%→57.7%
and D20 59.6%→63.2%, kept 2008/2022 bear-window hits ≥ 0.5, and gives a
directional call every day (coverage 86%→100%). No look-ahead: every feature
uses only closes up to the decision index.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from kospi_watcher.domain.agents.schemas import AgentFinding, Evidence
from kospi_watcher.domain.enums import Impact, MarketDirection, SourceType
from kospi_watcher.domain.money import DecimalNoFloat
from kospi_watcher.domain.time import now_utc

_MA = 100  # anchor SMA window (trading days)
_MOM = 60  # momentum lookback (trading days)
_STRUCT_FAST = 50  # trend-structure gate: SMA50 < SMA200 required for a bear call
_STRUCT_SLOW = 200
_BEAR_BAND = Decimal("0.03")  # bear needs a clear -3% breach of the 100-day line
_OVERSOLD = Decimal("0.10")  # >10% below the line = rebound zone, no bear-chasing
_DEFAULT_LONG_STRENGTH = 0.15  # conviction of an unconfirmed (default) long

# Acute-shock override: a sharp *recent* drop is risk-off regardless of the slow
# 100/200-day structure — a crash day must never read as strength. Keyed on price
# velocity (1-day / 3-day return), not the level, so it fires the moment the shock
# lands, before the slow averages can move. Thresholds ~ a 2-sigma+ KOSPI day.
_SHOCK_1D = Decimal("-0.035")  # a single-day drop of 3.5%+ = acute risk-off shock
_SHOCK_3D = Decimal("-0.06")  # a 3-day cumulative drop of 6%+ = sustained panic

# The signal needs the 200-day structure SMA before its first call.
TREND_WARMUP = _STRUCT_SLOW

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


def _sma(closes: Sequence[Decimal], i: int, w: int) -> Decimal:
    return sum(closes[i - w + 1 : i + 1], Decimal("0")) / Decimal(w)


def trend_core(
    closes: Sequence[Decimal], i: int
) -> tuple[int, float, Decimal | None, Decimal | None]:
    """Past-only trend at index ``i`` (inclusive). Returns (dir{-1,0,1}, strength,
    sma100, mom60). Bullish by default; bearish only on a confirmed downtrend
    (see the module docstring); 0 only during warmup."""
    if i < TREND_WARMUP:
        return 0, 0.0, None, None
    price = closes[i]
    sma = _sma(closes, i, _MA)
    mom = closes[i] / closes[i - _MOM] - Decimal("1")
    if sma == 0:
        return 0, 0.0, sma, mom
    dist = price / sma - Decimal("1")  # signed distance from the trend line

    # Acute-shock override (checked first): a sharp recent drop is decisively
    # risk-off — it must beat the bullish default AND the oversold-rebound
    # exemption, because a *fresh* crash differs from being chronically oversold.
    r1 = price / closes[i - 1] - Decimal("1")
    r3 = price / closes[i - 3] - Decimal("1")
    if r1 <= _SHOCK_1D or r3 <= _SHOCK_3D:
        strength = min(1.0, float(abs(r1)) * 10.0 + float(abs(r3)) * 4.0)
        return -1, max(strength, 0.5), sma, mom

    confirmed_bear = (
        -_OVERSOLD < dist < -_BEAR_BAND
        and mom < 0
        and _sma(closes, i, _STRUCT_FAST) < _sma(closes, i, _STRUCT_SLOW)
    )
    if confirmed_bear:
        strength = min(1.0, float(abs(dist)) * 8.0 + float(abs(mom)) * 3.0)
        return -1, strength, sma, mom

    if dist > 0:  # genuine uptrend: conviction scales with trend/momentum
        strength = min(1.0, float(dist) * 8.0 + max(float(mom), 0.0) * 3.0)
        return 1, max(strength, _DEFAULT_LONG_STRENGTH), sma, mom
    # Below the line but unconfirmed (or deeply oversold): weak default long.
    return 1, _DEFAULT_LONG_STRENGTH, sma, mom


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def build_trend_signal(closes: Sequence[Decimal], *, source: str) -> TrendSignal:
    """The latest trend signal from a close series (oldest→newest)."""
    if len(closes) <= TREND_WARMUP:
        return TrendSignal(
            direction=MarketDirection.NEUTRAL, strength=0.0, price=None, sma100=None,
            mom60_pct=None,
            note=f"시세 이력 부족({len(closes)}일 < {TREND_WARMUP + 1}일) — 추세 판단 보류.",
            source="none" if not closes else source,
        )
    i = len(closes) - 1
    d, strength, sma, mom = trend_core(closes, i)
    direction = (
        MarketDirection.BULLISH if d > 0
        else MarketDirection.BEARISH if d < 0
        else MarketDirection.NEUTRAL
    )
    mom_pct = _q2(mom * Decimal("100")) if mom is not None else None
    dist = (closes[i] / sma - Decimal("1")) if sma else Decimal("0")
    dist_pct = _q2(dist * Decimal("100"))
    r1_pct = _q2((closes[i] / closes[i - 1] - Decimal("1")) * Decimal("100"))
    r3_pct = _q2((closes[i] / closes[i - 3] - Decimal("1")) * Decimal("100"))
    is_shock = r1_pct <= _SHOCK_1D * 100 or r3_pct <= _SHOCK_3D * 100
    if direction is MarketDirection.BEARISH and is_shock:
        note = (
            f"1일 {r1_pct}%·3일 {r3_pct}% 급락 — 시장 충격/리스크오프 확인, "
            f"방어적 하락 전환 (강도 {strength:.0%})."
        )
    elif direction is MarketDirection.BEARISH:
        note = (
            f"100일선을 {abs(dist_pct)}% 이탈·60일 흐름 {mom_pct}%·"
            f"50일선<200일선(추세 구조 훼손) — 하락추세 확인 (강도 {strength:.0%})."
        )
    elif dist > 0:
        note = (
            f"주가가 100일선 위 +{dist_pct}%·60일 흐름 {mom_pct}% — "
            f"상승추세 (강도 {strength:.0%})."
        )
    elif dist <= -_OVERSOLD:
        note = (
            f"100일선 대비 {dist_pct}% 급락 구간 — 과매도 반등 우위로 "
            "조심스러운 강세 유지 (강도 낮음)."
        )
    else:
        note = (
            f"주가가 100일선 아래({dist_pct}%)지만 하락추세 확인 조건이 미충족 — "
            "기본 강세 유지 (강도 낮음)."
        )
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

    A NEUTRAL trend (warmup/no data) is a no-op (backward compatible). The override
    makes the desk-level signal — and thus the visible deliberation — track the
    real trend."""
    if signal.direction is MarketDirection.NEUTRAL:
        return list(findings)
    impact = Impact.HIGH if signal.strength >= 0.4 else Impact.MEDIUM
    confidence = min(0.9, 0.5 + signal.strength * 0.4)
    evidence = Evidence(
        source_id=f"trend-{signal.source}",
        source_type=SourceType.PRICE_DATA,
        title="100일 추세선·60일 흐름·50/200일 추세 구조",
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
                        "invalidation_conditions": [
                            "100일선 ±3% 재이탈",
                            "50·200일선 구조 전환",
                            "60일 모멘텀 부호 전환",
                        ],
                    }
                )
            )
        else:
            out.append(f)
    return out
