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
from kospi_watcher.domain.prediction.accuracy_track import Calibration
from kospi_watcher.domain.prediction.instruments import PREDICTION_UNIVERSE, stance_for
from kospi_watcher.domain.prediction.monetary_policy import (
    MonetaryPolicySignal,
    PolicyStance,
)
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
from kospi_watcher.domain.prediction.semiconductor import (
    SemiconductorSignal,
    SemiCycleStance,
)
from kospi_watcher.domain.prediction.trend_signal import TrendSignal
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

# Plain-language gloss of the direction for prose (avoids bare jargon).
_DIR_GLOSS: dict[MarketDirection, str] = {
    MarketDirection.BULLISH: "상승(강세)",
    MarketDirection.BEARISH: "하락(약세)",
    MarketDirection.NEUTRAL: "뚜렷한 방향성 부재(중립)",
}
_FORWARD_KO: dict[MarketDirection, str] = {
    MarketDirection.BULLISH: "오를 가능성",
    MarketDirection.BEARISH: "내릴 가능성",
    MarketDirection.NEUTRAL: "뚜렷한 방향 없이 등락을 반복할 가능성",
}

# Plain, readable description of each market phase (kept out of jargon territory).
_REGIME_PHRASE: dict[MarketRegime, str] = {
    MarketRegime.RISK_ON_STRONG: "위험자산 선호가 뚜렷한",
    MarketRegime.RISK_ON_FRAGILE: "위험자산을 선호하나 변동성이 큰",
    MarketRegime.LIQUIDITY_RALLY: "유동성에 기댄 상승",
    MarketRegime.EARNINGS_RALLY: "실적 기대가 이끄는 상승",
    MarketRegime.SIDEWAYS_LOW_VOL: "큰 변동 없이 방향을 탐색하는",
    MarketRegime.SIDEWAYS_HIGH_VOL: "변동성이 큰 채 방향이 엇갈리는",
    MarketRegime.RISK_OFF: "위험을 줄이려는 방어적인",
    MarketRegime.CRISIS: "위기 경계가 높은",
    MarketRegime.DATA_UNCERTAIN: "데이터가 불확실한",
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
            thesis=f"이번 전망({dir_ko})이 전망 기간 내 유지된다.",
            triggers=["주도 데스크 신호 지속", "수급·거시 환경 불변"],
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
    monetary_policy: MonetaryPolicySignal | None = None,
    semiconductor: SemiconductorSignal | None = None,
    trend_signal: TrendSignal | None = None,
    calibration: Calibration | None = None,
) -> MarketPrediction:
    as_of = as_of or now_utc()
    by_agent: dict[str, AgentFinding] = {}
    for f in findings:
        by_agent.setdefault(f.agent_name, f)

    desk_views = [_desk_view(d, by_agent) for d in AGENT_ORG]
    view_by_desk = {Desk(v.desk): v for v in desk_views}

    overall_score = sum(v.weight * v.score for v in desk_views)
    # The real price trend is the PRIMARY directional anchor (the prediction must
    # not fight the market); BOK monetary policy and the semiconductor mega-cap cycle
    # (index leadership ~1/3 of cap) are core tilts on top of it (ADR-025 / ADR-024 /
    # ADR-031). All adjust the desk-weighted score at the Chief level.
    overall_score += (
        _trend_tilt(trend_signal)
        + _policy_tilt(monetary_policy)
        + _semi_tilt(semiconductor)
    )
    # Auto-feedback: the calibration learned from scoring past predictions nudges
    # the direction toward the realized drift (ADR-027).
    if calibration is not None:
        overall_score += calibration.direction_bias
    direction = _lean(overall_score, _OVERALL_THR)
    confidence = _confidence(overall_score, direction, trend_signal, calibration)

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
    brief = _brief(
        direction,
        confidence,
        regime,
        view_by_desk,
        top_desk,
        stances,
        news_refs,
        trend_signal,
        monetary_policy,
        semiconductor,
        scenarios,
    )

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
        monetary_policy=monetary_policy,
        semiconductor=semiconductor,
        trend_signal=trend_signal,
        calibration=calibration,
        instrument_stances=stances,
        scenarios=scenarios,
        news_refs=news_refs,
        generated_by=generated_by,
        agent_count=agent_count,
        created_at=now_utc(),
    )


def _trend_clause(ts: TrendSignal) -> str:
    dir_ko = _DIR_KO[ts.direction]
    return (
        f"가격 추세가 100일 평균선과 최근 60일 흐름 기준으로 {dir_ko}이며"
        f"(추세 강도 {ts.strength:.0%}), 이번 판단을 시장의 실제 흐름에 맞췄다는 점이 가장 큽니다"
    )


def _confidence(
    overall_score: float,
    direction: MarketDirection,
    trend_signal: TrendSignal | None,
    calibration: Calibration | None,
) -> float:
    """Confidence from net signal agreement + the dominant trend's conviction,
    then anchored to the realized directional reliability (ADR-027).

    A clear, strongly-trending, empirically-reliable call should NOT read like a
    coin flip: the floor and slope are raised, an unambiguous aligned trend adds a
    conviction bonus, and the calibration pulls confidence toward the realized hit
    rate (e.g. ~0.7) rather than scaling it down."""
    conf = 0.42 + abs(overall_score) * 0.9
    if (
        trend_signal is not None
        and trend_signal.direction is direction
        and direction is not MarketDirection.NEUTRAL
    ):
        conf += 0.12 * trend_signal.strength  # strong aligned trend = real conviction
    conf = min(0.95, conf)
    # Reliability anchor: blend toward the realized hit rate FOR THIS DIRECTION
    # (bull calls anchor to the bull-call record, bear to bear — the by-direction
    # error results), then FLOOR at it — a call that is empirically right ~60% of
    # the time must never be reported below that rate (< 50% would misread as a
    # coin flip).
    if calibration is not None and direction is not MarketDirection.NEUTRAL:
        target = (
            calibration.bull_target
            if direction is MarketDirection.BULLISH
            else calibration.bear_target
        ) or calibration.confidence_target
        if target >= 0.5:
            conf = 0.6 * conf + 0.4 * target
            conf = max(conf, target)
    return round(min(0.95, conf), 2)


def _trend_tilt(ts: TrendSignal | None) -> float:
    """Signed house-level anchor to the real price trend (bull > 0, bear < 0).

    This is the PRIMARY directional driver — stronger than the policy tilt — so the
    house view tracks the actual market and doesn't fight a strong trend."""
    if ts is None or ts.direction is MarketDirection.NEUTRAL:
        return 0.0
    magnitude = min(0.35, 0.10 + ts.strength * 0.30)
    return _DIR_SIGN[ts.direction] * magnitude


def _policy_tilt(mp: MonetaryPolicySignal | None) -> float:
    """Signed house-level tilt from BOK policy (hawkish < 0, dovish > 0).

    BOK is a *core* driver: a confident hawkish/dovish read is strong enough to
    set the house direction even against the desk base. Confidence-weighted, with
    a small additional kick per expected hike, capped so it can't fully saturate.
    """
    if mp is None or mp.stance is PolicyStance.NEUTRAL:
        return 0.0
    magnitude = min(0.30, mp.confidence * (0.14 + 0.04 * abs(mp.expected_hikes_2026)))
    return _DIR_SIGN[mp.equity_bias] * magnitude


def _semi_tilt(semi: SemiconductorSignal | None) -> float:
    """Signed house-level tilt from the semiconductor cycle (downcycle < 0, up > 0).

    Samsung + SK hynix are ~1/3 of the index and its directional leadership, so a
    confident cycle read is a core tilt — strong enough to turn the house view
    defensive when the leaders roll over even while the slow index averages still
    point up (the rollover the trend anchor is too lagged to see, ADR-031).

    Sized proportionally to *how severe* the leadership move is: a ~1-month leader
    drawdown of -5% only nudges (a mild move should not override the trend anchor),
    but a -13%+ collapse (a genuine cycle break that is itself driving the index)
    is decisive enough to flip the house view defensive. Capped so it can't fully
    saturate the score. A config-override read (no momentum) is treated as a
    high-conviction manual call and sized to be decisive."""
    if semi is None or semi.stance is SemiCycleStance.NEUTRAL:
        return 0.0
    if semi.blended_mom_pct is not None:
        severity = abs(float(semi.blended_mom_pct)) / 100.0  # 1-month leader move
        magnitude = min(0.45, 0.14 + severity * 1.7)
    else:
        magnitude = min(0.45, semi.confidence * 0.50)
    return _DIR_SIGN[semi.equity_bias] * magnitude


def _policy_clause(mp: MonetaryPolicySignal) -> str:
    stance_ko = {
        PolicyStance.HAWKISH: "매파(긴축)",
        PolicyStance.DOVISH: "비둘기(완화)",
        PolicyStance.NEUTRAL: "중립",
    }[mp.stance]
    n = abs(mp.expected_hikes_2026)
    move = "인상" if mp.stance is PolicyStance.HAWKISH else "인하"
    path = f" 2026년 약 {n}회 {move} 전망," if n else ""
    bias_ko = _DIR_KO[mp.equity_bias]
    return (
        f"한국은행 통화정책은 {stance_ko} 기조로,{path} 코스피에 {bias_ko} 압력으로 "
        f"작용한다는 점도 핵심 거시 변수로 반영했습니다."
    )


def _semi_clause(semi: SemiconductorSignal) -> str:
    stance_ko = {
        SemiCycleStance.EXPANSION: "상승(업사이클)",
        SemiCycleStance.DOWNCYCLE: "하강(끝물)",
        SemiCycleStance.NEUTRAL: "중립",
    }[semi.stance]
    mom = (
        f" 최근 1개월 대장주 흐름 {semi.blended_mom_pct}%,"
        if semi.blended_mom_pct is not None
        else ""
    )
    bias_ko = _DIR_KO[semi.equity_bias]
    return (
        f"코스피 시총 약 1/3을 차지하는 삼성전자·SK하이닉스 반도체 메모리 사이클이 "
        f"{stance_ko} 국면으로,{mom} 지수에 {bias_ko} 압력으로 작용한다는 점을 "
        "핵심 동인으로 반영했습니다."
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
    trend_signal: TrendSignal | None,
    monetary_policy: MonetaryPolicySignal | None,
    semiconductor: SemiconductorSignal | None,
    scenarios: list[Scenario],
) -> str:
    """A structured, analyst-style note: 총평 → 핵심 동인 → 리스크 → 대응 전략 →
    지켜볼 변수. Plain Korean, professional but readable, written to actually help a
    decision. Paragraphs are separated by blank lines (rendered with `pre-line`)."""
    lead = view_by_desk[top_desk]
    risk = view_by_desk[Desk.RISK]
    by_symbol = {s.symbol: s for s in stances}
    long_ko = _stance_ko(by_symbol["069500"].label.value)
    inv_ko = _stance_ko(by_symbol["114800"].label.value)
    inv2_ko = _stance_ko(by_symbol["252670"].label.value)
    lead_driver = lead.top_drivers[0] if lead.top_drivers else "주도 신호"
    risk_driver = risk.top_drivers[0] if risk.top_drivers else "예상 밖 꼬리 위험"

    # 1) 총평 — the one-glance read (carries the subject label).
    overview = (
        f"【총평】 {_SUBJECT}에 대한 오늘의 종합 판단은 '{_DIR_GLOSS[direction]}'입니다. "
        f"분석 에이전트 21인이 5개 데스크로 나눠 검토하고 수석이 최종 조율한 결과로, "
        f"확신도는 {confidence:.0%}({_conv_ko(confidence)})이며 지금 장세는 "
        f"{_REGIME_PHRASE.get(regime, REGIME_KO[regime])} 국면으로 읽힙니다. "
        f"한마디로, 코스피는 단기적으로 {_FORWARD_KO[direction]}에 무게가 실립니다."
    )

    # 2) 핵심 동인 — why, in plain language (trend anchor → lead desk → policy → news).
    drivers: list[str] = []
    if trend_signal is not None and trend_signal.direction is not MarketDirection.NEUTRAL:
        drivers.append(f"무엇보다 {_trend_clause(trend_signal)}.")
    drivers.append(
        f"분석에서는 {lead.title}가 {_DIR_KO[lead.lean]} 신호를 주도했는데, "
        f"'{lead_driver}'가 핵심 논거입니다."
    )
    if semiconductor is not None and semiconductor.stance is not SemiCycleStance.NEUTRAL:
        drivers.append(_semi_clause(semiconductor))
    if monetary_policy is not None and monetary_policy.stance is not PolicyStance.NEUTRAL:
        drivers.append(_policy_clause(monetary_policy))
    else:
        drivers.append("금리·수급 등 거시 환경은 큰 변수 없이 중립적으로 반영했습니다.")
    if news_refs:
        drivers.append(
            f"여기에 최근 '{_trim(news_refs[0], 60)}' 등 뉴스 흐름도 같은 맥락으로 더해졌습니다."
        )
    movers = "【핵심 동인】 이렇게 본 근거는 다음과 같습니다. " + " ".join(drivers)

    # 3) 리스크 점검 — the other side, with the reversal odds + what would flip it.
    invalidation = {
        MarketDirection.BULLISH: (
            "외국인 매도 전환이나 변동성 급등이 나타나면 인버스로 방어 전환을 검토해야"
        ),
        MarketDirection.BEARISH: "낙폭이 과도해진 뒤의 기술적 반등 위험은 경계해야",
        MarketDirection.NEUTRAL: "방향이 확인되기 전까지 레버리지·인버스 모두 자제해야",
    }[direction]
    reversal = scenarios[1] if len(scenarios) > 1 else None
    rev_clause = (
        f"시나리오상 '{reversal.name}'이 약 {reversal.probability:.0%} 확률로 열려 있으며, "
        if reversal
        else ""
    )
    risks = (
        f"【리스크 점검】 반대 시각도 함께 봅니다. {risk.title}는 {_DIR_KO[risk.lean]} 관점에서 "
        f"'{risk_driver}'을(를) 경고합니다. {rev_clause}{invalidation} 합니다."
    )

    # 4) 대응 전략 — concrete positioning + a decay caution (carries '곱버스').
    action = {
        MarketDirection.BULLISH: (
            "오를 가능성에 무게가 실리는 만큼 지수형을 중심에 두되, "
            "단기 급등 구간에서는 한 번에 사기보다 나눠 접근하는 편이 안전합니다."
        ),
        MarketDirection.BEARISH: (
            "비중을 줄여 방어적으로 가져가되, 기술적 반등 위험이 있으니 "
            "인버스는 전량이 아니라 일부만 활용하는 편이 낫습니다."
        ),
        MarketDirection.NEUTRAL: (
            "한쪽으로 베팅하기보다 비중을 낮추고 관망하다가, "
            "방향이 잡힌 뒤에 대응하는 것이 유리합니다."
        ),
    }[direction]
    strategy = (
        f"【대응 전략】 지수형(KODEX 200)·레버리지는 {long_ko}, 인버스는 {inv_ko}, "
        f"곱버스(2배 인버스)는 {inv2_ko}로 제시합니다. {action} "
        "특히 레버리지·곱버스는 매일 재조정에서 생기는 손실이 쌓여 오래 들고 갈수록 "
        "불리하니, 길게 보유하기보다 짧게 대응하는 것이 원칙입니다."
    )

    # 5) 지켜볼 변수 — concrete checkpoints to monitor next.
    watch = (
        "【지켜볼 변수】 앞으로는 외국인·기관 수급의 방향, 코스피 변동성지수의 급변, "
        f"환율·금리 관련 일정, 그리고 {lead.title}의 신호 지속 여부를 함께 점검하시기 바랍니다."
    )

    return "\n\n".join([overview, movers, risks, strategy, watch])
