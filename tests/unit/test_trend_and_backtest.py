"""Unit tests for the price-trend anchor + accuracy backtest (ADR-025)."""

from __future__ import annotations

from decimal import Decimal

from kospi_watcher.domain.agents.schemas import AgentFinding
from kospi_watcher.domain.enums import (
    DataQuality,
    Horizon,
    Impact,
    MarketDirection,
)
from kospi_watcher.domain.prediction.backtest import run_backtest
from kospi_watcher.domain.prediction.synthesizer import synthesize
from kospi_watcher.domain.prediction.trend_signal import (
    TREND_AGENT,
    apply_trend_to_findings,
    build_trend_signal,
)
from kospi_watcher.domain.time import now_utc


def _rising(n: int = 160) -> list[Decimal]:
    return [Decimal(str(round(100 * (1.004 ** k), 2))) for k in range(n)]


def _falling(n: int = 160) -> list[Decimal]:
    return [Decimal(str(round(300 * (0.996 ** k), 2))) for k in range(n)]


def _flat(n: int = 160) -> list[Decimal]:
    return [Decimal("100") for _ in range(n)]


def _finding(name: str, direction: MarketDirection = MarketDirection.NEUTRAL) -> AgentFinding:
    t = now_utc()
    return AgentFinding(
        agent_name=name, agent_version="0", as_of=t, horizon=Horizon.D5,
        direction=direction, impact=Impact.MEDIUM, confidence=0.5, thesis="x",
        data_quality=DataQuality.OK, model_name="mock", prompt_version="0", created_at=t,
    )


def test_build_trend_signal_directions() -> None:
    assert build_trend_signal(_rising(), source="yahoo").direction is MarketDirection.BULLISH
    assert build_trend_signal(_falling(), source="yahoo").direction is MarketDirection.BEARISH
    assert build_trend_signal(_flat(), source="yahoo").direction is MarketDirection.NEUTRAL


def test_build_trend_signal_features() -> None:
    s = build_trend_signal(_rising(), source="yahoo")
    assert s.price is not None and s.sma100 is not None
    assert s.price > s.sma100  # uptrend: price above its 100-day average
    assert s.mom60_pct is not None and s.mom60_pct > 0
    assert 0.0 < s.strength <= 1.0


def test_apply_trend_overrides_technical_agent() -> None:
    findings = [_finding(TREND_AGENT), _finding("Korea Macro Agent")]
    s = build_trend_signal(_rising(), source="yahoo")
    out = {f.agent_name: f for f in apply_trend_to_findings(findings, s)}
    assert out[TREND_AGENT].direction is MarketDirection.BULLISH
    assert out["Korea Macro Agent"].direction is MarketDirection.NEUTRAL  # untouched


def test_apply_trend_noop_when_neutral() -> None:
    findings = [_finding(TREND_AGENT)]
    s = build_trend_signal(_flat(), source="yahoo")
    assert apply_trend_to_findings(findings, s) == findings


def test_strong_aligned_trend_raises_confidence() -> None:
    # A clear, strong, aligned uptrend should NOT read like a coin flip (>= 0.6).
    ts = build_trend_signal(_rising(), source="yahoo")
    pred = synthesize([], trend_signal=ts)
    assert pred.direction is MarketDirection.BULLISH
    assert pred.confidence >= 0.6


def test_backtest_report_shape() -> None:
    # A long, mostly-rising series → high base rate; report stays well-formed.
    closes = _rising(500)
    rep = run_backtest(closes, symbol="KOSPI", source="yahoo", as_of=now_utc())
    assert len(rep.train) == 3 and len(rep.test) == 3
    assert rep.primary_horizon_days == 20
    for h in rep.test:
        assert 0.0 <= h.hit_rate <= 1.0
        assert 0.0 <= h.base_rate <= 1.0
        assert h.skill == round(h.hit_rate - h.base_rate, 4)
    assert "1개월" in rep.interpretation
    assert "train" in rep.interpretation  # the verdict now anchors on the train split
