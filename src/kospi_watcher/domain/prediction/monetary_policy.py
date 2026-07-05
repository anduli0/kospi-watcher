"""BOK (한국은행) monetary-policy signal — a core macro driver (ADR-024).

The prediction engine must treat Korean monetary policy (금통위 의사록·BOK 리포트·
기준금리 결정·총재 발언) as a first-class input. A *hawkish* BOK (rate hikes)
is a headwind for KOSPI valuations (esp. rate-sensitive growth/2차전지/바이오) and
favours inverse/곱버스; a *dovish* BOK is the opposite.

This module produces a :class:`MonetaryPolicySignal` from either an **authoritative
config override** (the user states the stance, e.g. HAWKISH + 2~3 hikes) or, in
``auto`` mode, a **deterministic keyword classifier over BOK-related news
headlines** (keyless, immediate — picks up governor statements as they hit the
wire). It then injects that stance into the MACRO desk by overriding the
**Korea Macro** and **Rates and Liquidity** agents' findings, so the whole
synthesis (direction → regime → 인버스/곱버스 stances → brief) reflects BOK policy.

Honest sourcing: ``source`` is "config" (authoritative), "news" (headline-derived),
or "mock". Full 금통위 의사록/BOK 리포트 NLP parsing is the upgrade path behind the
same signal interface.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.agents.schemas import AgentFinding, Evidence
from kospi_watcher.domain.enums import (
    Impact,
    MarketDirection,
    SourceType,
)
from kospi_watcher.domain.time import now_utc

# Agents whose findings carry the BOK stance into the MACRO desk.
MACRO_LEAD_AGENT = "Korea Macro Agent"
RATES_AGENT = "Rates and Liquidity Agent"
_POLICY_AGENTS = (MACRO_LEAD_AGENT, RATES_AGENT)


class PolicyStance(StrEnum):
    HAWKISH = "HAWKISH"  # tightening / rate hikes
    NEUTRAL = "NEUTRAL"  # on hold / data-dependent
    DOVISH = "DOVISH"  # easing / rate cuts


class MonetaryPolicySignal(BaseModel):
    """The house read on BOK monetary policy and its KOSPI implication."""

    model_config = ConfigDict(extra="forbid")

    stance: PolicyStance
    expected_hikes_2026: int  # net 25bp moves expected in 2026 (negative = cuts)
    equity_bias: MarketDirection  # what it implies for KOSPI (hawkish → BEARISH)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    drivers: list[str] = Field(default_factory=list)  # headline snippets used
    source: str  # "config" | "news" | "mock"
    as_of: AwareDatetime


# Headlines must mention one of these to count as a BOK-policy signal.
# Keys are matched space-insensitively (Korean headlines write 금리인상/금리 인상 both),
# so phrases here are written WITHOUT spaces and compared against a despaced headline.
_BOK_CONTEXT = ("금리", "한국은행", "한은", "금통위", "기준금리", "통화정책")
# Weighted hawkish / dovish phrases (despaced Korean). Avoid the bare "인상"/"인하"
# (too ambiguous — e.g. "인상적") and anchor on rate-specific compounds.
_HAWKISH: dict[str, int] = {
    "금리인상": 3,
    "인상전환": 3,
    "인상모드": 3,
    "추가인상": 3,
    "인상시사": 2,
    "인상가능성": 2,
    "인상기조": 2,
    "인상압력": 2,
    "고금리장기화": 2,
    "긴축": 2,
    "매파": 2,
}
_DOVISH: dict[str, int] = {
    "금리인하": 3,
    "인하전환": 3,
    "추가인하": 3,
    "인하시사": 2,
    "인하가능성": 2,
    "인하기조": 2,
    "피벗": 2,
    "완화": 2,
    "비둘기": 2,
}

_EQUITY_BIAS: dict[PolicyStance, MarketDirection] = {
    PolicyStance.HAWKISH: MarketDirection.BEARISH,
    PolicyStance.NEUTRAL: MarketDirection.NEUTRAL,
    PolicyStance.DOVISH: MarketDirection.BULLISH,
}


def _classify_headlines(
    headlines: Sequence[str],
) -> tuple[int, int, list[str]]:
    """Return (net hawkish-minus-dovish score, relevant count, driver snippets)."""
    net = 0
    relevant = 0
    drivers: list[str] = []
    for h in headlines:
        hn = h.replace(" ", "")  # space-insensitive (금리인상 == 금리 인상)
        if not any(ctx in hn for ctx in _BOK_CONTEXT):
            continue
        relevant += 1
        hw = sum(w for kw, w in _HAWKISH.items() if kw in hn)
        dv = sum(w for kw, w in _DOVISH.items() if kw in hn)
        if hw != dv:
            net += hw - dv
            drivers.append(h.strip())
    return net, relevant, drivers[:4]


def build_signal(
    *,
    stance_override: str = "auto",
    hikes_override: int = 0,
    headlines: Sequence[str] | None = None,
    as_of: AwareDatetime | None = None,
) -> MonetaryPolicySignal:
    """Build the BOK signal from an authoritative override or headline auto-mode."""
    as_of = as_of or now_utc()
    ov = (stance_override or "auto").strip().lower()

    if ov in ("hawkish", "dovish", "neutral"):
        stance = PolicyStance[ov.upper()]
        hikes = hikes_override
        if stance is PolicyStance.HAWKISH and hikes <= 0:
            hikes = 2
        if stance is PolicyStance.DOVISH and hikes >= 0:
            hikes = -1
        return MonetaryPolicySignal(
            stance=stance,
            expected_hikes_2026=hikes,
            equity_bias=_EQUITY_BIAS[stance],
            confidence=0.8,
            rationale=_rationale(stance, hikes, source="config"),
            drivers=[],
            source="config",
            as_of=as_of,
        )

    # auto — derive from BOK news headlines
    net, relevant, drivers = _classify_headlines(headlines or [])
    if relevant == 0:
        return MonetaryPolicySignal(
            stance=PolicyStance.NEUTRAL,
            expected_hikes_2026=0,
            equity_bias=MarketDirection.NEUTRAL,
            confidence=0.4,
            rationale=(
                "최근 BOK 통화정책 관련 헤드라인이 부족해 중립으로 둠. "
                "MONETARY_POLICY_STANCE로 직접 지정 가능."
            ),
            drivers=[],
            source="news",
            as_of=as_of,
        )

    thr = 2
    if net >= thr:
        stance = PolicyStance.HAWKISH
        hikes = max(1, min(3, round(net / 3)))
    elif net <= -thr:
        stance = PolicyStance.DOVISH
        hikes = -max(1, min(3, round(-net / 3)))
    else:
        stance = PolicyStance.NEUTRAL
        hikes = 0
    confidence = min(0.85, 0.45 + abs(net) * 0.06)
    return MonetaryPolicySignal(
        stance=stance,
        expected_hikes_2026=hikes,
        equity_bias=_EQUITY_BIAS[stance],
        confidence=round(confidence, 2),
        rationale=_rationale(stance, hikes, source="news"),
        drivers=drivers,
        source="news",
        as_of=as_of,
    )


def _rationale(stance: PolicyStance, hikes: int, *, source: str) -> str:
    src_ko = "사용자 지정" if source == "config" else "BOK 관련 뉴스 헤드라인 분석"
    if stance is PolicyStance.HAWKISH:
        return (
            f"한국은행 매파 기조({src_ko}): 2026년 약 {abs(hikes)}회 인상 전망. "
            "고금리 장기화는 코스피 밸류에이션·금리민감 성장주(2차전지·바이오 등)에 "
            "부담 → 지수 약세 압력, 인버스/곱버스 우위."
        )
    if stance is PolicyStance.DOVISH:
        return (
            f"한국은행 완화 기조({src_ko}): 2026년 약 {abs(hikes)}회 인하 전망. "
            "유동성 개선은 밸류에이션·위험선호에 우호 → 지수 강세, 롱 우위."
        )
    return (
        f"한국은행 중립/관망({src_ko}): 동결 또는 데이터 의존적 스탠스로 "
        "방향성 영향은 제한적."
    )


def _policy_finding(base: AgentFinding, signal: MonetaryPolicySignal) -> AgentFinding:
    """Override an existing MACRO finding so it carries the BOK stance."""
    impact = (
        Impact.HIGH
        if signal.stance is not PolicyStance.NEUTRAL
        and (abs(signal.expected_hikes_2026) >= 2 or signal.confidence >= 0.6)
        else Impact.MEDIUM
    )
    sectors = (
        ["2차전지", "바이오", "성장주", "증권", "건설"]
        if signal.stance is PolicyStance.HAWKISH
        else ["반도체", "성장주", "증권"]
        if signal.stance is PolicyStance.DOVISH
        else []
    )
    title = signal.drivers[0] if signal.drivers else "BOK 통화정책 스탠스"
    evidence = Evidence(
        source_id=f"bok-policy-{signal.source}",
        source_type=SourceType.MACRO_RELEASE,
        title=title[:120],
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
            "affected_sectors": sectors,
            "invalidation_conditions": [
                "BOK 스탠스 반전(인상↔인하)" ,
                "물가·환율 경로의 예상 밖 변화",
            ],
        }
    )


def apply_to_findings(
    findings: Sequence[AgentFinding], signal: MonetaryPolicySignal
) -> list[AgentFinding]:
    """Return findings with the two MACRO policy agents overridden by ``signal``.

    A NEUTRAL stance is a no-op (the pipeline is unchanged when there is no
    directional BOK signal). Non-target findings always pass through unchanged."""
    if signal.stance is PolicyStance.NEUTRAL:
        return list(findings)
    out: list[AgentFinding] = []
    for f in findings:
        if f.agent_name in _POLICY_AGENTS:
            out.append(_policy_finding(f, signal))
        else:
            out.append(f)
    return out
