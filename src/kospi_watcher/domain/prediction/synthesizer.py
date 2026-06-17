"""Hierarchical synthesis: agent findings → desk views → house prediction.

Pure and deterministic for a given set of findings, so it works identically over
mock or LLM findings and is fully testable. The desks vote (impact x confidence,
lead-weighted), the Chief combines desk views by desk weight, a regime is
classified, instrument stances (long/inverse/곱버스) are derived, scenarios are
sized, and a single-narrative daily brief is composed.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from kospi_watcher.domain.agents.org import (
    AGENT_ORG,
    DIRECTIONAL_DESKS,
    Desk,
    DeskSpec,
)
from kospi_watcher.domain.agents.schemas import AgentFinding
from kospi_watcher.domain.enums import (
    DataQuality,
    Horizon,
    Impact,
    MarketDirection,
    MarketRegime,
)
from kospi_watcher.domain.prediction.instruments import PREDICTION_UNIVERSE, stance_for
from kospi_watcher.domain.prediction.regime import REGIME_KO, classify_regime
from kospi_watcher.domain.prediction.schemas import (
    AgentPosition,
    ChiefDeliberation,
    Deliberation,
    DeskDeliberation,
    DeskView,
    InstrumentStance,
    MarketPrediction,
    Scenario,
)
from kospi_watcher.domain.time import now_utc

_SUBJECT = "코스피200 지수 방향 (KODEX 200 추종 기준)"
_HORIZON_LABEL: dict[Horizon, str] = {
    Horizon.INTRADAY: "장중 (인트라데이)",
    Horizon.D1: "초단기 (1거래일, D1)",
    Horizon.D5: "단기 (약 1주, D5)",
    Horizon.D20: "중기 (약 1개월, D20)",
    Horizon.STRUCTURAL: "구조적 (장기)",
}

_IMPACT_W: dict[Impact, float] = {Impact.LOW: 1.0, Impact.MEDIUM: 2.0, Impact.HIGH: 3.0}
_DIR_SIGN: dict[MarketDirection, int] = {
    MarketDirection.BULLISH: 1,
    MarketDirection.BEARISH: -1,
    MarketDirection.NEUTRAL: 0,
}
_LEAD_BONUS = 1.5
_DESK_THR = 0.15
_OVERALL_THR = 0.12
_HIGH, _MED = 0.55, 0.35

_DIR_KO: dict[MarketDirection, str] = {
    MarketDirection.BULLISH: "강세",
    MarketDirection.BEARISH: "약세",
    MarketDirection.NEUTRAL: "중립",
}


def _conv_ko(confidence: float) -> str:
    return "고확신" if confidence >= _HIGH else "중간확신" if confidence >= _MED else "저확신"


def _lean(score: float, thr: float) -> MarketDirection:
    if score > thr:
        return MarketDirection.BULLISH
    if score < -thr:
        return MarketDirection.BEARISH
    return MarketDirection.NEUTRAL


def _desk_view(desk: DeskSpec, by_agent: dict[str, AgentFinding]) -> DeskView:
    contributions: list[float] = []
    weights: list[float] = []
    drivers: list[tuple[float, str]] = []
    for name in desk.members:
        finding = by_agent.get(name)
        if finding is None:
            continue
        w = _IMPACT_W[finding.impact] * (_LEAD_BONUS if name == desk.lead else 1.0)
        contributions.append(_DIR_SIGN[finding.direction] * w * finding.confidence)
        weights.append(w)
        drivers.append((w * finding.confidence, finding.thesis))

    responded = len(weights)
    score = sum(contributions) / sum(weights) if weights else 0.0
    lean = _lean(score, _DESK_THR)
    conviction = min(1.0, abs(score))
    top = [t for _, t in sorted(drivers, key=lambda x: x[0], reverse=True)][:2]
    summary = (
        f"{desk.title_ko}: {responded}/{len(desk.members)}개 에이전트 → "
        f"{_DIR_KO[lean]} (확신 {conviction:.0%})"
    )
    return DeskView(
        desk=desk.key.value,
        title=desk.title_ko,
        lean=lean,
        conviction=round(conviction, 3),
        weight=desk.weight,
        score=round(score, 3),
        member_count=len(desk.members),
        responded=responded,
        summary=summary,
        top_drivers=[_trim(t) for t in top],
    )


def _trim(text: str, limit: int = 90) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _scenarios(direction: MarketDirection, confidence: float) -> list[Scenario]:
    c = confidence
    p_cont = 0.34 + 0.30 * c
    p_rev = 0.20 + 0.10 * (1 - c)
    p_side = 1.0 - p_cont - p_rev
    ps = [round(p_cont, 2), round(p_rev, 2), round(p_side, 2)]
    big = ps.index(max(ps))
    ps[big] = round(1.0 - sum(p for i, p in enumerate(ps) if i != big), 2)

    dir_ko = _DIR_KO[direction]
    rev_ko = {
        MarketDirection.BULLISH: "약세 반전",
        MarketDirection.BEARISH: "낙폭과대 반등",
        MarketDirection.NEUTRAL: "방향 이탈",
    }[direction]
    return [
        Scenario(
            name=f"기본 — {dir_ko} 지속",
            probability=ps[0],
            thesis=f"하우스 뷰({dir_ko})가 horizon 내 유지된다.",
            triggers=["주도 데스크 신호 지속", "수급/거시 환경 불변"],
        ),
        Scenario(
            name=f"반전 — {rev_ko}",
            probability=ps[1],
            thesis=f"촉매 등장으로 {rev_ko}이 전개된다.",
            triggers=["외국인 수급 전환", "변동성(VKOSPI) 급변", "예상 밖 거시 서프라이즈"],
        ),
        Scenario(
            name="횡보 — 방향성 부재",
            probability=ps[2],
            thesis="뚜렷한 촉매 없이 박스권에 머문다.",
            triggers=["거래대금 위축", "이벤트 대기"],
        ),
    ]


def _opposes(a: MarketDirection, b: MarketDirection) -> bool:
    return {a, b} == {MarketDirection.BULLISH, MarketDirection.BEARISH}


def _short(name: str) -> str:
    return name.replace(" Agent", "")


def _desk_deliberation(
    desk: DeskSpec, by_agent: dict[str, AgentFinding], view: DeskView
) -> DeskDeliberation:
    positions: list[AgentPosition] = []
    for name in desk.members:
        finding = by_agent.get(name)
        if finding is None:
            continue
        positions.append(
            AgentPosition(
                agent=name,
                is_lead=name == desk.lead,
                direction=finding.direction,
                confidence=round(finding.confidence, 2),
                note=_trim(finding.thesis, 70),
            )
        )
    consensus = view.lean
    aligned = [p for p in positions if p.direction == consensus]
    agreement = round(len(aligned) / len(positions), 2) if positions else 0.0
    dissent = [p.agent for p in positions if _opposes(p.direction, consensus)]
    dnote = (
        f", 이견 {len(dissent)}건({', '.join(_short(d) for d in dissent)})은 리드가 가중·조율"
        if dissent
        else ", 이견 없음"
    )
    lead_note = (
        f"{desk.lead}(리드): {len(aligned)}/{len(positions)}건 "
        f"{_DIR_KO[consensus]} 합의{dnote}."
    )
    return DeskDeliberation(
        desk=desk.key.value,
        title=desk.title_ko,
        consensus=consensus,
        agreement=agreement,
        positions=positions,
        dissent=dissent,
        lead_note=lead_note,
    )


def _chief_deliberation(
    directional_views: list[DeskView], direction: MarketDirection, confidence: float
) -> ChiefDeliberation:
    aligned = [
        v.title
        for v in directional_views
        if v.lean == direction and direction is not MarketDirection.NEUTRAL
    ]
    conflicted = [v.title for v in directional_views if _opposes(v.lean, direction)]
    aligned_w = sum(v.weight for v in directional_views if v.lean == direction)
    if direction is MarketDirection.NEUTRAL:
        note = f"수석 신디사이저: 데스크 간 방향이 엇갈려 중립으로 종합(확신 {confidence:.0%})."
    else:
        note = (
            f"수석 신디사이저: {len(aligned)}개 데스크가 {_DIR_KO[direction]}를 지지"
            f"(가중 {aligned_w:.0%}), {len(conflicted)}개 데스크는 이견. "
            f"데스크 가중 종합 결과 {_DIR_KO[direction]}로 확정(확신 {confidence:.0%})."
        )
    return ChiefDeliberation(
        overall=direction, aligned_desks=aligned, conflicted_desks=conflicted, note=note
    )


def synthesize(
    findings: Sequence[AgentFinding],
    *,
    as_of: datetime | None = None,
    horizon: Horizon = Horizon.D5,
    generated_by: str = "mock",
    agent_count: int = 21,
    news_headlines: Sequence[str] | None = None,
) -> MarketPrediction:
    as_of = as_of or now_utc()
    by_agent: dict[str, AgentFinding] = {}
    for f in findings:
        by_agent.setdefault(f.agent_name, f)

    desk_views = [_desk_view(d, by_agent) for d in AGENT_ORG]
    view_by_desk = {Desk(v.desk): v for v in desk_views}

    overall_score = sum(v.weight * v.score for v in desk_views)
    direction = _lean(overall_score, _OVERALL_THR)
    confidence = round(min(0.95, 0.40 + abs(overall_score) * 0.8), 2)

    vol = by_agent.get("Volatility and Regime Agent")
    vol_high = vol is not None and vol.impact is Impact.HIGH
    red = by_agent.get("Red-Team and Risk Agent")
    risk_high = (
        red is not None and red.impact is Impact.HIGH and red.direction is MarketDirection.BEARISH
    )
    di_members = next(d for d in AGENT_ORG if d.key is Desk.DATA_INTEGRITY).members
    data_quals = [by_agent[m].data_quality for m in di_members if m in by_agent]
    data_ok = all(q in (DataQuality.OK, DataQuality.PARTIAL) for q in data_quals)
    overall_dq = DataQuality.OK if data_ok else DataQuality.PARTIAL

    top_desk_spec = max(
        DIRECTIONAL_DESKS,
        key=lambda d: abs(d.weight * view_by_desk[d.key].score),
    )
    top_desk = top_desk_spec.key
    regime = classify_regime(
        direction=direction,
        confidence=confidence,
        vol_high=vol_high,
        risk_high=risk_high,
        data_ok=data_ok,
        top_desk=top_desk,
    )

    stances = [
        InstrumentStance(
            symbol=inst.symbol,
            name=inst.name,
            kind=inst.kind,
            **stance_for(inst.kind, direction, confidence, regime).__dict__,
        )
        for inst in PREDICTION_UNIVERSE
    ]
    scenarios = _scenarios(direction, confidence)
    news_refs = [h for h in (news_headlines or []) if h][:5]
    headline = _headline(direction, confidence, regime)
    brief = _brief(direction, confidence, regime, view_by_desk, top_desk, stances, news_refs)

    analysis_desks = [d for d in AGENT_ORG if d.key is not Desk.CHIEF]
    deliberation = Deliberation(
        desks=[_desk_deliberation(d, by_agent, view_by_desk[d.key]) for d in analysis_desks],
        chief=_chief_deliberation(
            [view_by_desk[d.key] for d in DIRECTIONAL_DESKS], direction, confidence
        ),
    )

    return MarketPrediction(
        prediction_id=uuid.uuid4().hex,
        as_of=as_of,
        subject=_SUBJECT,
        horizon=horizon,
        horizon_label=_HORIZON_LABEL[horizon],
        regime=regime,
        direction=direction,
        confidence=confidence,
        data_quality=overall_dq,
        headline=headline,
        brief=brief,
        desk_views=desk_views,
        deliberation=deliberation,
        instrument_stances=stances,
        scenarios=scenarios,
        news_refs=news_refs,
        generated_by=generated_by,
        agent_count=agent_count,
        created_at=now_utc(),
    )


def _headline(direction: MarketDirection, confidence: float, regime: MarketRegime) -> str:
    base = f"코스피 {_DIR_KO[direction]}·{_conv_ko(confidence)} — {REGIME_KO[regime]} 국면"
    if direction is MarketDirection.BEARISH:
        return base + " · 인버스 우위"
    if direction is MarketDirection.BULLISH:
        return base + " · 인버스 비중축소"
    return base


def _stance_ko(label: str) -> str:
    return {
        "OVERWEIGHT": "비중확대",
        "NEUTRAL": "중립",
        "UNDERWEIGHT": "비중축소",
        "AVOID": "회피",
    }[label]


def _brief(
    direction: MarketDirection,
    confidence: float,
    regime: MarketRegime,
    view_by_desk: dict[Desk, DeskView],
    top_desk: Desk,
    stances: list[InstrumentStance],
    news_refs: list[str],
) -> str:
    dir_ko = _DIR_KO[direction]
    lead = view_by_desk[top_desk]
    risk = view_by_desk[Desk.RISK]
    by_symbol = {s.symbol: s for s in stances}
    long_ko = _stance_ko(by_symbol["069500"].label.value)
    inv_ko = _stance_ko(by_symbol["114800"].label.value)
    inv2_ko = _stance_ko(by_symbol["252670"].label.value)
    lead_driver = lead.top_drivers[0] if lead.top_drivers else "주도 신호"
    risk_driver = risk.top_drivers[0] if risk.top_drivers else "꼬리위험"

    invalidation = {
        MarketDirection.BULLISH: "외국인 수급 전환이나 변동성 급등 시 인버스로의 헤지 전환을 검토",
        MarketDirection.BEARISH: "낙폭과대에 따른 기술적 반등 위험은 경계",
        MarketDirection.NEUTRAL: "방향 확정 전까지 레버리지 상품은 회피",
    }[direction]

    news_clause = (
        f" 최근 '{_trim(news_refs[0], 50)}' 등 뉴스 흐름도 함께 반영했다."
        if news_refs
        else ""
    )

    return (
        f"[예측 대상: {_SUBJECT}] 오늘 코스피는 {REGIME_KO[regime]} 국면으로 판단된다. "
        f"21개 분석 에이전트를 5개 데스크로 계층 종합(데스크 토의→수석 조율)한 하우스 뷰는 "
        f"{dir_ko}이며 확신도는 {confidence:.0%}다.{news_clause} "
        f"{lead.title}가 {_DIR_KO[lead.lean]} 신호를 주도했고({lead_driver}), "
        f"이는 종합 방향성의 핵심 근거가 됐다. 다만 {risk.title}는 {_DIR_KO[risk.lean]} 시각에서 "
        f"{risk_driver}을(를) 경고하며, {invalidation}한다. "
        f"포지셔닝은 KODEX 200·레버리지 {long_ko}, 인버스 {inv_ko}, "
        f"곱버스(200선물인버스2X) {inv2_ko}로 제시한다."
    )
