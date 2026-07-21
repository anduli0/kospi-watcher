"""Semiconductor mega-cap cycle signal — a core index driver (ADR-031).

Samsung Electronics (005930) and SK hynix (000660) together are ~1/3 of the
KOSPI's market cap and the market's directional leadership: when the memory cycle
rolls over, the two mega-caps sell off and drag the index with them — a move the
slow 100/200-day index trend (``trend_signal.py``) is too lagged to see (a sharp
leadership rollover happens while the long index averages are still rising).

This module produces a :class:`SemiconductorSignal` from either an **authoritative
config override** (the owner states the cycle, e.g. DOWNCYCLE = memory 끝물) or, in
``auto`` mode, the **real ~1-month price momentum of the two leaders** (keyless
Yahoo, blended). A downcycle read is a KOSPI headwind (favours inverse/곱버스); an
expansion read is a tailwind. It tilts the house view at the Chief level and
overrides the FUNDAMENTAL desk's Technology and Semiconductor agent finding.

Honest sourcing/skill: ``source`` is "config" (authoritative), "price"
(momentum-derived), or "mock" (offline → NEUTRAL no-op). Like the trend anchor
(ADR-029), the leader-momentum signal does not beat a bull-market base rate on raw
hit rate; its job is **regime alignment** — turning the house view defensive when
the index's own leadership breaks down. Full DRAM/NAND spot-price & inventory
cycle data is the upgrade path behind this same signal interface.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.agents.schemas import AgentFinding, Evidence
from kospi_watcher.domain.enums import Impact, MarketDirection, SourceType
from kospi_watcher.domain.time import now_utc

# The FUNDAMENTAL-desk agent whose finding carries the semiconductor cycle read.
SEMI_AGENT = "Technology and Semiconductor Agent"

# ~1-month (trading days) leadership momentum window — responsive enough to catch a
# rollover the slow index averages miss, long enough not to whip on daily noise.
MOM_WINDOW = 21
# Blend weight: Samsung is the larger index weight, SK hynix the purer memory play.
_W_SAMSUNG = Decimal("0.5")
_W_HYNIX = Decimal("0.5")
# A move of ±5% over ~1 month in the leaders is a directional cycle read.
_BAND = Decimal("0.05")


class SemiCycleStance(StrEnum):
    EXPANSION = "EXPANSION"  # memory upcycle — leadership rising
    NEUTRAL = "NEUTRAL"  # range-bound / mixed
    DOWNCYCLE = "DOWNCYCLE"  # memory 끝물 — leadership rolling over


class SemiconductorSignal(BaseModel):
    """The house read on the semiconductor mega-cap cycle and its KOSPI implication."""

    model_config = ConfigDict(extra="forbid")

    stance: SemiCycleStance
    equity_bias: MarketDirection  # what it implies for KOSPI (downcycle → BEARISH)
    samsung_mom_pct: Decimal | None  # signed ~1-month momentum, %
    hynix_mom_pct: Decimal | None
    blended_mom_pct: Decimal | None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    source: str  # "config" | "price" | "mock"
    as_of: AwareDatetime


_EQUITY_BIAS: dict[SemiCycleStance, MarketDirection] = {
    SemiCycleStance.EXPANSION: MarketDirection.BULLISH,
    SemiCycleStance.NEUTRAL: MarketDirection.NEUTRAL,
    SemiCycleStance.DOWNCYCLE: MarketDirection.BEARISH,
}


def _mom(closes: Sequence[Decimal], window: int) -> Decimal | None:
    """Signed momentum over ``window`` trading days, or None if too short."""
    if len(closes) <= window or closes[-1 - window] == 0:
        return None
    return closes[-1] / closes[-1 - window] - Decimal("1")


def _q2(v: Decimal) -> Decimal:
    return (v * Decimal("100")).quantize(Decimal("0.01"))


def build_signal(
    *,
    stance_override: str = "auto",
    samsung_closes: Sequence[Decimal] | None = None,
    hynix_closes: Sequence[Decimal] | None = None,
    as_of: AwareDatetime | None = None,
) -> SemiconductorSignal:
    """Build the semiconductor cycle signal from an override or leader momentum."""
    as_of = as_of or now_utc()
    ov = (stance_override or "auto").strip().lower()

    if ov in ("expansion", "up", "upcycle", "downcycle", "down", "neutral"):
        stance = (
            SemiCycleStance.EXPANSION
            if ov in ("expansion", "up", "upcycle")
            else SemiCycleStance.DOWNCYCLE
            if ov in ("downcycle", "down")
            else SemiCycleStance.NEUTRAL
        )
        return SemiconductorSignal(
            stance=stance,
            equity_bias=_EQUITY_BIAS[stance],
            samsung_mom_pct=None,
            hynix_mom_pct=None,
            blended_mom_pct=None,
            confidence=0.8,
            rationale=_rationale(stance, None, source="config"),
            source="config",
            as_of=as_of,
        )

    # auto — derive from the real ~1-month momentum of the two leaders.
    sm = _mom(samsung_closes or [], MOM_WINDOW)
    hm = _mom(hynix_closes or [], MOM_WINDOW)
    if sm is None or hm is None:
        return SemiconductorSignal(
            stance=SemiCycleStance.NEUTRAL,
            equity_bias=MarketDirection.NEUTRAL,
            samsung_mom_pct=None,
            hynix_mom_pct=None,
            blended_mom_pct=None,
            confidence=0.4,
            rationale=(
                "삼성전자·SK하이닉스 시세 이력이 부족해 반도체 사이클 판단 보류. "
                "SEMICONDUCTOR_CYCLE_STANCE로 직접 지정 가능."
            ),
            source="mock",
            as_of=as_of,
        )

    blended = _W_SAMSUNG * sm + _W_HYNIX * hm
    if blended <= -_BAND:
        stance = SemiCycleStance.DOWNCYCLE
    elif blended >= _BAND:
        stance = SemiCycleStance.EXPANSION
    else:
        stance = SemiCycleStance.NEUTRAL
    confidence = min(0.85, 0.45 + float(abs(blended)) * 2.0)
    return SemiconductorSignal(
        stance=stance,
        equity_bias=_EQUITY_BIAS[stance],
        samsung_mom_pct=_q2(sm),
        hynix_mom_pct=_q2(hm),
        blended_mom_pct=_q2(blended),
        confidence=round(confidence, 2),
        rationale=_rationale(stance, _q2(blended), source="price"),
        source="price",
        as_of=as_of,
    )


def _rationale(
    stance: SemiCycleStance, blended_pct: Decimal | None, *, source: str
) -> str:
    src_ko = "사용자 지정" if source == "config" else "삼성전자·SK하이닉스 1개월 모멘텀"
    mom_ko = f" (지수 대장주 {blended_pct}%)" if blended_pct is not None else ""
    if stance is SemiCycleStance.DOWNCYCLE:
        return (
            f"반도체 메모리 사이클 하강({src_ko}){mom_ko}: 코스피 시총 약 1/3을 차지하는 "
            "삼성전자·SK하이닉스 대장주가 꺾이면 지수 자체가 눌린다 → 지수 약세 압력, "
            "인버스/곱버스 우위. 느린 지수 이동평균이 놓치는 주도주 이탈을 반영."
        )
    if stance is SemiCycleStance.EXPANSION:
        return (
            f"반도체 메모리 사이클 상승({src_ko}){mom_ko}: 대장주(삼성전자·SK하이닉스) "
            "주도 상승은 지수를 끌어올린다 → 지수 강세, 롱 우위."
        )
    return (
        f"반도체 대장주 방향성 중립({src_ko}){mom_ko}: 주도주 모멘텀이 뚜렷하지 않아 "
        "방향성 영향은 제한적."
    )


def _semi_finding(base: AgentFinding, signal: SemiconductorSignal) -> AgentFinding:
    """Override the Technology and Semiconductor finding with the cycle read."""
    impact = (
        Impact.HIGH
        if signal.stance is not SemiCycleStance.NEUTRAL and signal.confidence >= 0.55
        else Impact.MEDIUM
    )
    evidence = Evidence(
        source_id=f"semi-cycle-{signal.source}",
        source_type=SourceType.PRICE_DATA,
        title="삼성전자·SK하이닉스 대장주 모멘텀 (반도체 메모리 사이클)",
        published_at=signal.as_of,
        available_at=signal.as_of,
        claim=signal.rationale,
    )
    return base.model_copy(
        update={
            "direction": signal.equity_bias,
            "impact": impact,
            "confidence": signal.confidence,
            "thesis": signal.rationale,
            "evidence": [evidence],
            "affected_symbols": ["005930", "000660"],
            "affected_sectors": ["반도체", "IT"],
            "invalidation_conditions": [
                "삼성전자·SK하이닉스 1개월 모멘텀 부호 전환",
                "DRAM/NAND 현물가·재고 사이클 반전",
            ],
        }
    )


def apply_to_findings(
    findings: Sequence[AgentFinding], signal: SemiconductorSignal
) -> list[AgentFinding]:
    """Return findings with the Semiconductor agent overridden by ``signal``.

    A NEUTRAL cycle is a no-op (backward compatible). Non-target findings always
    pass through unchanged."""
    if signal.stance is SemiCycleStance.NEUTRAL:
        return list(findings)
    out: list[AgentFinding] = []
    for f in findings:
        if f.agent_name == SEMI_AGENT:
            out.append(_semi_finding(f, signal))
        else:
            out.append(f)
    return out
