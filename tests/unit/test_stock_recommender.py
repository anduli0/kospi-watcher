"""Unit tests for the individual-stock recommender (ADR-026)."""

from __future__ import annotations

from decimal import Decimal

from kospi_watcher.domain.enums import MarketDirection, MarketRegime
from kospi_watcher.domain.prediction.monetary_policy import PolicyStance
from kospi_watcher.domain.stocks import (
    STOCK_UNIVERSE,
    HouseContext,
    StockHorizon,
    StockSignal,
    recommend,
)
from kospi_watcher.domain.time import now_utc

_META = {m.code: m for m in STOCK_UNIVERSE}


def _sig(
    code: str,
    *,
    mom: str | None = None,
    above: bool = True,
    news: str | None = None,
    stretch: str = "10",
) -> StockSignal:
    m = Decimal(mom) if mom is not None else None
    return StockSignal(
        meta=_META[code], price=Decimal("100000"),
        mom20=m, mom60=m, mom120=m,
        above_ma20=above, above_ma60=above, above_ma120=above,
        stretch_pct=Decimal(stretch),
        sector_change_pct=Decimal("2.0"), news_hit=news,
    )


def _ctx(direction=MarketDirection.BULLISH, stance=PolicyStance.HAWKISH) -> HouseContext:
    return HouseContext(direction, MarketRegime.RISK_ON_FRAGILE, stance)


def test_report_has_three_horizons_with_picks() -> None:
    signals = [_sig(m.code, mom="5") for m in STOCK_UNIVERSE]
    rep = recommend(signals, _ctx(), as_of=now_utc(), price_source="yahoo")
    assert [h.horizon for h in rep.horizons] == [
        StockHorizon.SHORT, StockHorizon.MID, StockHorizon.LONG
    ]
    for h in rep.horizons:
        assert 1 <= len(h.picks) <= 5
        assert [p.rank for p in h.picks] == list(range(1, len(h.picks) + 1))


def test_high_momentum_name_ranks_top_short() -> None:
    signals = [_sig(m.code, mom="2") for m in STOCK_UNIVERSE]
    # Give 삼성전자 a huge 20d momentum + a news catalyst.
    signals = [s for s in signals if s.meta.code != "005930"]
    signals.append(_sig("005930", mom="20", news="삼성전자 신고가 경신"))
    rep = recommend(signals, _ctx(), as_of=now_utc(), price_source="yahoo")
    short = next(h for h in rep.horizons if h.horizon is StockHorizon.SHORT)
    assert short.picks[0].code == "005930"
    assert short.picks[0].news_catalyst is not None


def test_hawkish_bok_ranks_bank_above_same_momentum_growth() -> None:
    # Equal momentum bank (BENEFIT) vs growth (HIGH rate-sensitivity): under a
    # hawkish BOK the bank should rank ahead on the mid horizon, with a benefit note.
    signals = [_sig("105560", mom="3"), _sig("035720", mom="3")]  # KB금융 vs 카카오
    rep = recommend(
        signals, _ctx(stance=PolicyStance.HAWKISH), as_of=now_utc(), price_source="yahoo"
    )
    mid = next(h for h in rep.horizons if h.horizon is StockHorizon.MID)
    order = [p.code for p in mid.picks]
    assert order.index("105560") < order.index("035720")
    bank = next(p for p in mid.picks if p.code == "105560")
    assert any("은행" in d for d in bank.drivers)


def test_long_horizon_rewards_structural_themes() -> None:
    # No momentum at all → long picks should be theme-driven (semis/defense/nuclear).
    signals = [_sig(m.code, mom=None) for m in STOCK_UNIVERSE]
    rep = recommend(signals, _ctx(), as_of=now_utc(), price_source="yahoo")
    long = next(h for h in rep.horizons if h.horizon is StockHorizon.LONG)
    top_themes = {t for p in long.picks for t in p.themes}
    assert top_themes & {"AI반도체", "HBM", "2차전지", "방산", "원전"}


def test_overheated_name_ranks_below_healthy_peer_short() -> None:
    # Same sector & momentum, but one is far above its 120-day trend (과열): the
    # overextended name should rank lower short-term (reversion/bubble risk), and
    # surface the overheat note + flag.
    cool = _sig("005930", mom="15", stretch="12")  # 삼성전자, healthy uptrend
    hot = _sig("000660", mom="15", stretch="70")  # SK하이닉스, very stretched
    rep = recommend([cool, hot], _ctx(), as_of=now_utc(), price_source="yahoo")
    short = next(h for h in rep.horizons if h.horizon is StockHorizon.SHORT)
    order = [p.code for p in short.picks]
    assert order.index("005930") < order.index("000660")
    hot_pick = next(p for p in short.picks if p.code == "000660")
    assert hot_pick.overheated is True
    assert any("이격" in d for d in hot_pick.drivers)


def test_picks_carry_detail() -> None:
    signals = [_sig(m.code, mom="6") for m in STOCK_UNIVERSE]
    rep = recommend(signals, _ctx(), as_of=now_utc(), price_source="yahoo")
    for h in rep.horizons:
        for p in h.picks:
            assert len(p.detail) > 20  # a real per-horizon explanation


def test_deterministic() -> None:
    signals = [_sig(m.code, mom="4") for m in STOCK_UNIVERSE]
    a = recommend(signals, _ctx(), as_of=now_utc(), price_source="yahoo")
    b = recommend(signals, _ctx(), as_of=now_utc(), price_source="yahoo")
    assert [p.code for p in a.horizons[0].picks] == [p.code for p in b.horizons[0].picks]
