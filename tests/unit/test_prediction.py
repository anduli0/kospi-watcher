"""Prediction synthesis + instrument-stance logic (long / inverse / 곱버스)."""

from __future__ import annotations

from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.registry import AgentRegistry
from kospi_watcher.domain.enums import (
    InstrumentKind,
    MarketDirection,
    MarketRegime,
    StanceLabel,
)
from kospi_watcher.domain.prediction.instruments import stance_for
from kospi_watcher.domain.prediction.synthesizer import synthesize
from kospi_watcher.domain.time import now_utc


def _mock_findings() -> list:
    runs = AgentRegistry().run_all(AgentContext(as_of=now_utc(), universe=("069500",)))
    return [f for r in runs for f in r.findings]


# --- stance logic ---


def test_bearish_high_conviction_favours_inverse() -> None:
    d, c, r = MarketDirection.BEARISH, 0.7, MarketRegime.RISK_OFF
    assert stance_for(InstrumentKind.LONG_1X, d, c, r).label is StanceLabel.AVOID
    assert stance_for(InstrumentKind.LONG_2X, d, c, r).label is StanceLabel.AVOID
    assert stance_for(InstrumentKind.INVERSE_1X, d, c, r).label is StanceLabel.OVERWEIGHT
    inv2 = stance_for(InstrumentKind.INVERSE_2X, d, c, r)
    assert inv2.label is StanceLabel.OVERWEIGHT  # 곱버스 favoured when bearish & trending
    assert inv2.risk_note is not None  # leverage/decay warning always present


def test_bullish_high_conviction_avoids_inverse() -> None:
    d, c, r = MarketDirection.BULLISH, 0.7, MarketRegime.RISK_ON_STRONG
    assert stance_for(InstrumentKind.LONG_1X, d, c, r).label is StanceLabel.OVERWEIGHT
    assert stance_for(InstrumentKind.INVERSE_1X, d, c, r).label is StanceLabel.AVOID
    assert stance_for(InstrumentKind.INVERSE_2X, d, c, r).label is StanceLabel.AVOID


def test_neutral_view_underweights_leverage() -> None:
    d, c, r = MarketDirection.NEUTRAL, 0.3, MarketRegime.SIDEWAYS_LOW_VOL
    assert stance_for(InstrumentKind.INVERSE_1X, d, c, r).label is StanceLabel.NEUTRAL
    assert stance_for(InstrumentKind.LONG_2X, d, c, r).label is StanceLabel.UNDERWEIGHT


def test_crisis_caps_leveraged_inverse() -> None:
    # Even aligned (bearish) the 곱버스 is too dangerous in a crisis regime.
    s = stance_for(InstrumentKind.INVERSE_2X, MarketDirection.BEARISH, 0.8, MarketRegime.CRISIS)
    assert s.label is StanceLabel.AVOID


# --- full synthesis ---


def test_synthesis_structure_over_mock() -> None:
    pred = synthesize(_mock_findings(), generated_by="mock")
    assert len(pred.desk_views) == 6
    assert {v.desk for v in pred.desk_views} == {
        "DATA_INTEGRITY",
        "MACRO",
        "FLOW_TECH",
        "FUNDAMENTAL",
        "RISK",
        "CHIEF",
    }
    # all 21 mock agents responded
    assert sum(v.responded for v in pred.desk_views) == 21
    # 4 instrument stances on the long/short ladder
    assert {s.symbol for s in pred.instrument_stances} == {"069500", "122630", "114800", "252670"}
    # 3 scenarios summing to 1.0
    assert len(pred.scenarios) == 3
    assert abs(sum(s.probability for s in pred.scenarios) - 1.0) < 1e-6
    # the brief is one narrative mentioning the 곱버스 stance
    assert "곱버스" in pred.brief
    assert len(pred.brief) > 120
    assert pred.headline


def test_synthesis_includes_deliberation() -> None:
    pred = synthesize(_mock_findings(), generated_by="mock")
    delib = pred.deliberation
    assert delib is not None
    # 5 analysis desks deliberate (data-integrity + the 4 directional); Chief is separate.
    assert len(delib.desks) == 5
    assert all(d.positions for d in delib.desks)
    assert all(d.lead_note for d in delib.desks)
    # Chief reconciles to the same overall direction as the prediction.
    assert delib.chief.overall is pred.direction
    assert delib.chief.note


def test_brief_reflects_news_and_subject() -> None:
    pred = synthesize(
        _mock_findings(),
        generated_by="mock",
        news_headlines=["[TEST] 코스피 외국인 순매수 전환"],
    )
    assert pred.news_refs == ["[TEST] 코스피 외국인 순매수 전환"]
    assert "[TEST] 코스피 외국인 순매수 전환" in pred.brief
    assert pred.subject in pred.brief  # the prediction subject is labeled
    assert pred.horizon_label  # horizon is labeled


def test_synthesis_stances_consistent_with_direction() -> None:
    pred = synthesize(_mock_findings(), generated_by="mock")
    by_symbol = {s.symbol: s for s in pred.instrument_stances}
    long_lbl = by_symbol["069500"].label
    inv_lbl = by_symbol["114800"].label
    if pred.direction is MarketDirection.BULLISH:
        assert long_lbl is not StanceLabel.AVOID
        assert inv_lbl is not StanceLabel.OVERWEIGHT
    elif pred.direction is MarketDirection.BEARISH:
        assert inv_lbl is not StanceLabel.AVOID
