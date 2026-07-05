"""Deterministic individual-stock recommender (ADR-026).

Scores a curated universe into short / mid / long-term top picks by combining
**real per-stock price momentum** with the site's house view (direction/regime),
the live **sector board**, **BOK monetary policy**, structural **themes**, and
**news catalysts**. Pure & deterministic; no look-ahead in the inputs (the
service computes momentum from past closes). Bold but reasoned — the UI carries
the disclaimer. No ``float`` for prices; ratios stay float.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from pydantic import AwareDatetime

from kospi_watcher.domain.enums import MarketDirection, MarketRegime
from kospi_watcher.domain.prediction.monetary_policy import PolicyStance
from kospi_watcher.domain.stocks.schemas import (
    HorizonRecommendation,
    StockHorizon,
    StockPick,
    StockRecommendationReport,
)
from kospi_watcher.domain.stocks.universe import STRUCTURAL_THEMES, StockMeta


@dataclass
class StockSignal:
    """Per-stock computed features (built by the service from live data)."""

    meta: StockMeta
    price: Decimal | None
    mom20: Decimal | None  # 20-day return, %
    mom60: Decimal | None
    mom120: Decimal | None
    above_ma20: bool
    above_ma60: bool
    above_ma120: bool
    stretch_pct: Decimal | None  # price vs 120-day SMA, % (overextension / 과열 proxy)
    sector_change_pct: Decimal | None  # the stock's sector live board move, %
    news_hit: str | None  # a recent headline mentioning the name, if any


@dataclass(frozen=True)
class HouseContext:
    direction: MarketDirection
    regime: MarketRegime
    monetary_stance: PolicyStance


_RISK_OFF = frozenset({MarketRegime.RISK_OFF, MarketRegime.CRISIS})
_RISK_ON = frozenset(
    {MarketRegime.RISK_ON_STRONG, MarketRegime.LIQUIDITY_RALLY, MarketRegime.EARNINGS_RALLY}
)

_HORIZON_META = {
    StockHorizon.SHORT: (
        "단기 (1~4주)",
        "최근 가격 모멘텀·섹터 강세·뉴스 촉매 중심. 변동성이 크므로 분할매수·손절 전제로 본다.",
    ),
    StockHorizon.MID: (
        "중기 (1~3개월)",
        "섹터 추세·실적 모멘텀에 하우스 방향과 금리(BOK) 환경을 반영한다.",
    ),
    StockHorizon.LONG: (
        "장기 (6~12개월)",
        "AI반도체·2차전지·방산·원전·조선 등 구조적 성장 테마와 장기 추세를 중심으로 본다.",
    ),
}

_DISCLAIMER = (
    "개별 종목 추천은 가격 모멘텀·섹터·하우스 뷰·금리·뉴스를 결합한 결정론적 모델의 "
    "참고 의견이며, 투자자문이나 매매 권유가 아닙니다. 과감한 비중 표현도 모델 산출일 뿐 "
    "수익을 보장하지 않으며, 투자 판단과 책임은 전적으로 이용자 본인에게 있습니다."
)


# Overextension: how far above its 120-day trend a name has run. Beyond these
# thresholds the move is "too hot" — momentum may persist, but reversion / bubble
# risk rises, so we penalise it (heaviest short-term, lightest long-term).
_OVERHEAT_THRESH = 35.0  # % above 120-day SMA = very extended (bubble/reversion risk)


def _stretch(s: StockSignal) -> float:
    return float(s.stretch_pct) if s.stretch_pct is not None else 0.0


def _overheat_penalty(s: StockSignal, base: float, weight: float) -> tuple[float, str | None]:
    """Penalty for running too far above the long-term trend. Returns (penalty>=0,
    overheat note if very extended)."""
    st = _stretch(s)
    excess = st - base
    if excess <= 0:
        return 0.0, None
    note = f"120일선 +{st:.0f}% 이격(과열·되돌림 위험)" if st >= _OVERHEAT_THRESH else None
    return excess * weight, note


def _norm(x: Decimal | None, scale: float) -> float:
    if x is None:
        return 0.0
    v = float(x) / scale
    return max(-1.3, min(1.3, v))


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _bok_adjust(meta: StockMeta, stance: PolicyStance, weight: float) -> tuple[float, str | None]:
    """How BOK policy helps/hurts this name. Returns (score, driver-note)."""
    if stance is PolicyStance.HAWKISH:
        if meta.rate_sensitivity == "BENEFIT":
            return weight, "매파 BOK 수혜(은행 순이자마진 개선)"
        if meta.rate_sensitivity == "HIGH":
            return -weight, "매파 BOK 부담(고밸류·금리민감)"
        return -weight * 0.2, None
    if stance is PolicyStance.DOVISH:
        if meta.rate_sensitivity == "HIGH":
            return weight, "완화적 BOK 수혜(성장주 밸류 회복)"
        if meta.rate_sensitivity == "BENEFIT":
            return -weight * 0.5, None
        return weight * 0.2, None
    return 0.0, None


def _beta_regime(meta: StockMeta, ctx: HouseContext, weight: float) -> tuple[float, str | None]:
    if meta.beta != "HIGH":
        return 0.0, None
    if ctx.direction is MarketDirection.BULLISH or ctx.regime in _RISK_ON:
        return weight, "위험선호 국면 고베타 수혜"
    if ctx.direction is MarketDirection.BEARISH or ctx.regime in _RISK_OFF:
        return -weight, "위험회피 국면 고베타 부담"
    return 0.0, None


def _struct_themes(meta: StockMeta) -> list[str]:
    return [t for t in meta.themes if t in STRUCTURAL_THEMES]


def _score_short(s: StockSignal, ctx: HouseContext) -> tuple[float, list[str]]:
    d: list[str] = []
    score = _norm(s.mom20, 12.0) * 1.4
    if s.mom20 is not None and s.mom20 >= Decimal("4"):
        d.append(f"20일 모멘텀 {_q2(s.mom20):+}%")
    score += 0.5 if s.above_ma20 else -0.4
    if s.above_ma20:
        d.append("20일선 상회(단기 상승추세)")
    if s.sector_change_pct is not None:
        score += _norm(s.sector_change_pct, 2.5) * 0.6
        if s.sector_change_pct >= Decimal("1"):
            d.append(f"{s.meta.sector_ko} 섹터 강세({_q2(s.sector_change_pct):+}%)")
    if s.news_hit:
        score += 0.8
        d.append("뉴스 촉매")
    bscore, bnote = _beta_regime(s.meta, ctx, 0.4)
    score += bscore
    if bnote and bscore > 0:
        d.append(bnote)
    # Overextension: reversion risk is highest near-term → heaviest penalty.
    pen, onote = _overheat_penalty(s, base=20.0, weight=0.022)
    score -= pen
    if onote:
        d.insert(0, onote)  # surface the overheat/reversion risk first
    return score, d


def _score_mid(s: StockSignal, ctx: HouseContext) -> tuple[float, list[str]]:
    d: list[str] = []
    score = _norm(s.mom60, 25.0) * 1.1
    if s.mom60 is not None and s.mom60 >= Decimal("8"):
        d.append(f"60일 모멘텀 {_q2(s.mom60):+}%")
    score += 0.5 if s.above_ma60 else -0.4
    if s.above_ma60:
        d.append("60일선 상회(중기 추세)")
    if s.sector_change_pct is not None:
        score += _norm(s.sector_change_pct, 2.5) * 0.4
    if ctx.direction is MarketDirection.BULLISH:
        score += 0.5
    elif ctx.direction is MarketDirection.BEARISH:
        score -= 0.5
    bscore, bnote = _bok_adjust(s.meta, ctx.monetary_stance, 0.6)
    score += bscore
    if bnote:
        d.append(bnote)
    themes = _struct_themes(s.meta)
    if themes:
        score += 0.3
    pen, onote = _overheat_penalty(s, base=28.0, weight=0.013)
    score -= pen
    if onote:
        d.insert(0, onote)  # surface the overheat/reversion risk first
    return score, d


def _score_long(s: StockSignal, ctx: HouseContext) -> tuple[float, list[str]]:
    d: list[str] = []
    score = _norm(s.mom120, 40.0) * 0.6
    score += 0.4 if s.above_ma120 else -0.3
    if s.above_ma120:
        d.append("120일선 상회(장기 추세)")
    themes = _struct_themes(s.meta)
    if themes:
        score += min(1.2, 0.55 * len(themes))
        d.append(f"{'·'.join(themes)} 구조적 성장 수혜")
    bscore, bnote = _bok_adjust(s.meta, ctx.monetary_stance, 0.7)
    score += bscore
    if bnote:
        d.append(bnote)
    bscore2, _ = _beta_regime(s.meta, ctx, 0.3)
    score += bscore2
    if ctx.direction is MarketDirection.BULLISH:
        score += 0.3
    elif ctx.direction is MarketDirection.BEARISH:
        score -= 0.3
    # Long-term: structural growth can sustain a premium, so only extreme stretch
    # is penalised (lightly).
    pen, onote = _overheat_penalty(s, base=45.0, weight=0.007)
    score -= pen
    if onote:
        d.insert(0, onote)  # surface the overheat/reversion risk first
    return score, d


_SCORERS = {
    StockHorizon.SHORT: (_score_short, lambda s: s.mom20),
    StockHorizon.MID: (_score_mid, lambda s: s.mom60),
    StockHorizon.LONG: (_score_long, lambda s: s.mom120),
}


def _conviction(score: float) -> str:
    if score >= 2.0:
        return "적극매수"
    if score >= 1.0:
        return "매수"
    return "관심"


_DIR_KO = {
    MarketDirection.BULLISH: "강세",
    MarketDirection.BEARISH: "약세",
    MarketDirection.NEUTRAL: "중립",
}


def _bok_text(meta: StockMeta, stance: PolicyStance) -> str:
    if stance is PolicyStance.HAWKISH:
        if meta.rate_sensitivity == "BENEFIT":
            return "매파 BOK가 순이자마진에 우호적"
        if meta.rate_sensitivity == "HIGH":
            return "매파 BOK(고금리)가 밸류에이션에 부담"
        return "BOK 영향은 중립적"
    if stance is PolicyStance.DOVISH:
        if meta.rate_sensitivity == "HIGH":
            return "완화적 BOK가 성장주 밸류 회복에 우호적"
        return "BOK 영향은 제한적"
    return "BOK는 중립"


def _detail(horizon: StockHorizon, s: StockSignal, ctx: HouseContext) -> str:
    m = s.meta
    st = _stretch(s)
    overheated = st >= _OVERHEAT_THRESH
    themes = "·".join(m.themes)

    if horizon is StockHorizon.SHORT:
        lead: list[str] = []
        if s.mom20 is not None and s.mom20 >= Decimal("4"):
            lead.append(f"최근 20거래일 {_q2(s.mom20):+}% 단기 모멘텀")
        if s.above_ma20:
            lead.append("20일선 위 단기 상승추세")
        if s.sector_change_pct is not None and s.sector_change_pct >= Decimal("1"):
            lead.append(f"{m.sector_ko} 섹터 당일 강세")
        if s.news_hit:
            lead.append("뉴스 촉매")
        body = (
            f"{m.name}은(는) "
            + (", ".join(lead) if lead else "복합 단기 신호")
            + "에 힘입어 단기 상승 가능성이 부각됩니다."
        )
        body += (
            f" 다만 120일선 +{st:.0f}% 이격의 과열 구간이라 차익실현·되돌림 위험이 크므로, "
            "추격보다는 분할매수·짧은 손절을 전제로 접근하세요."
            if overheated
            else " 과열 부담은 제한적이라 눌림목 분할매수가 유효합니다."
        )
        return body

    if horizon is StockHorizon.MID:
        trend = f"60일 추세({_q2(s.mom60):+}%)" if s.mom60 is not None else "추세"
        sector_themes = m.sector_ko + (f"·{themes}" if themes else "")
        body = (
            f"{m.name}은(는) 중기적으로 {sector_themes} 업황과 {trend}가 유효합니다. "
            f"시장 하우스 뷰는 {_DIR_KO[ctx.direction]}, {_bok_text(m, ctx.monetary_stance)}."
        )
        body += (
            f" 단, 120일선 +{st:.0f}% 이격으로 밸류 부담이 있어 비중은 분할·점진적으로 가져가세요."
            if overheated
            else " 과열은 크지 않아 추세 추종에 무게를 둘 수 있습니다."
        )
        return body

    # LONG
    if themes:
        body = (
            f"{m.name}의 장기 핵심 동력은 {themes} 구조적 성장입니다. "
            f"장기 추세는 {'유효' if s.above_ma120 else '약화'}한 상태"
        )
    else:
        body = (
            f"{m.name}의 장기 관점은 {m.sector_ko} 업황과 장기 가격 추세에 달려 있습니다. "
            f"장기 추세는 {'유효' if s.above_ma120 else '약화'}한 상태"
        )
    body += (
        f"로, 단기 과열(120일선 +{st:.0f}%)에도 추세가 살아있어 "
        "분할·장기 관점에서 접근합니다."
        if overheated
        else "이며, 과열 부담이 크지 않아 장기 추세 추종에 무게를 둡니다."
    )
    return body


def _rationale(name: str, conviction: str, drivers: list[str]) -> str:
    head = "·".join(drivers[:2]) if drivers else "복합 신호"
    return f"{name}: {head} → {conviction} 의견."


def _pick(
    rank: int,
    s: StockSignal,
    score: float,
    drivers: list[str],
    mom: Decimal | None,
    horizon: StockHorizon,
    ctx: HouseContext,
) -> StockPick:
    conviction = _conviction(score)
    return StockPick(
        rank=rank,
        code=s.meta.code,
        name=s.meta.name,
        sector=s.meta.sector_ko,
        themes=list(s.meta.themes),
        price=s.price,
        momentum_pct=_q2(mom) if mom is not None else None,
        stretch_pct=_q2(s.stretch_pct) if s.stretch_pct is not None else None,
        overheated=_stretch(s) >= _OVERHEAT_THRESH,
        conviction=conviction,
        score=round(score, 3),
        drivers=drivers[:4],
        rationale=_rationale(s.meta.name, conviction, drivers),
        detail=_detail(horizon, s, ctx),
        news_catalyst=s.news_hit,
    )


def recommend(
    signals: list[StockSignal],
    ctx: HouseContext,
    *,
    as_of: AwareDatetime,
    price_source: str,
    top_n: int = 5,
) -> StockRecommendationReport:
    horizons: list[HorizonRecommendation] = []
    for horizon, (scorer, mom_of) in _SCORERS.items():
        scored = [(s, *scorer(s, ctx)) for s in signals]
        scored.sort(key=lambda t: t[1], reverse=True)
        label, approach = _HORIZON_META[horizon]
        picks = [
            _pick(i + 1, s, score, drivers, mom_of(s), horizon, ctx)
            for i, (s, score, drivers) in enumerate(scored[:top_n])
        ]
        horizons.append(
            HorizonRecommendation(
                horizon=horizon, label=label, approach=approach, picks=picks
            )
        )
    return StockRecommendationReport(
        as_of=as_of,
        house_direction=ctx.direction,
        house_regime=ctx.regime,
        monetary_stance=ctx.monetary_stance.value,
        universe_size=len(signals),
        price_source=price_source,
        horizons=horizons,
        disclaimer=_DISCLAIMER,
    )
