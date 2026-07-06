"""Unit tests for the price-trend anchor + accuracy backtest (ADR-025/029).

The recalibrated signal is bullish-by-default: bearish requires a *confirmed*
downtrend (clear -3% breach of the 100-day line + negative 60-day momentum +
SMA50 < SMA200), and a >10% oversold breach returns to a weak default long
(rebound zone) instead of chasing further downside.
"""

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
    TREND_WARMUP,
    apply_trend_to_findings,
    build_trend_signal,
)
from kospi_watcher.domain.time import now_utc


def _rising(n: int = 260) -> list[Decimal]:
    return [Decimal(str(round(100 * (1.004**k), 4))) for k in range(n)]


def _deep_fall(n: int = 260) -> list[Decimal]:
    # Steady -0.4%/day: ends ~18% below the 100-day SMA — the oversold zone.
    return [Decimal(str(round(300 * (0.996**k), 4))) for k in range(n)]


def _confirmed_bear() -> list[Decimal]:
    # 200 flat days, then 60 days of -0.15%/day: ~-6% below the 100-day SMA
    # (inside the bear band), negative momentum, SMA50 < SMA200.
    return [Decimal("100")] * 200 + [
        Decimal(str(round(100 * (0.9985**k), 4))) for k in range(1, 61)
    ]


def _flat(n: int = 260) -> list[Decimal]:
    return [Decimal("100") for _ in range(n)]


def _finding(name: str, direction: MarketDirection = MarketDirection.NEUTRAL) -> AgentFinding:
    t = now_utc()
    return AgentFinding(
        agent_name=name, agent_version="0", as_of=t, horizon=Horizon.D5,
        direction=direction, impact=Impact.MEDIUM, confidence=0.5, thesis="x",
        data_quality=DataQuality.OK, model_name="mock", prompt_version="0", created_at=t,
    )


def test_uptrend_is_bullish() -> None:
    s = build_trend_signal(_rising(), source="yahoo")
    assert s.direction is MarketDirection.BULLISH
    assert s.strength > 0.5  # clear trend = real conviction


def test_confirmed_downtrend_is_bearish() -> None:
    s = build_trend_signal(_confirmed_bear(), source="yahoo")
    assert s.direction is MarketDirection.BEARISH
    assert s.strength > 0.3
    assert "하락추세 확인" in s.note


def test_deep_oversold_returns_weak_default_long() -> None:
    # >10% below the line = rebound-variance zone: no bear-chasing.
    s = build_trend_signal(_deep_fall(), source="yahoo")
    assert s.direction is MarketDirection.BULLISH
    assert s.strength <= 0.2  # weak conviction, honestly labelled
    assert "급락 구간" in s.note


def test_flat_market_is_weak_default_long() -> None:
    s = build_trend_signal(_flat(), source="yahoo")
    assert s.direction is MarketDirection.BULLISH
    assert s.strength <= 0.2


def test_warmup_is_neutral() -> None:
    s = build_trend_signal(_flat(TREND_WARMUP - 50), source="yahoo")
    assert s.direction is MarketDirection.NEUTRAL
    assert s.strength == 0.0


def test_build_trend_signal_features() -> None:
    s = build_trend_signal(_rising(), source="yahoo")
    assert s.price is not None and s.sma100 is not None
    assert s.price > s.sma100  # uptrend: price above its 100-day average
    assert s.mom60_pct is not None and s.mom60_pct > 0
    assert 0.0 < s.strength <= 1.0


def test_apply_trend_overrides_technical_agent() -> None:
    findings = [_finding(TREND_AGENT), _finding("Korea Macro Agent")]
    s = build_trend_signal(_confirmed_bear(), source="yahoo")
    out = {f.agent_name: f for f in apply_trend_to_findings(findings, s)}
    assert out[TREND_AGENT].direction is MarketDirection.BEARISH
    assert out["Korea Macro Agent"].direction is MarketDirection.NEUTRAL  # untouched


def test_apply_trend_noop_when_neutral() -> None:
    findings = [_finding(TREND_AGENT)]
    s = build_trend_signal(_flat(150), source="yahoo")  # warmup → NEUTRAL
    assert apply_trend_to_findings(findings, s) == findings


def test_strong_aligned_trend_raises_confidence() -> None:
    # A clear, strong, aligned uptrend should NOT read like a coin flip (>= 0.6).
    ts = build_trend_signal(_rising(), source="yahoo")
    pred = synthesize([], trend_signal=ts)
    assert pred.direction is MarketDirection.BULLISH
    assert pred.confidence >= 0.6


def test_backtest_report_shape() -> None:
    # A long, mostly-rising series → high base rate; report stays well-formed.
    closes = _rising(600)
    rep = run_backtest(closes, symbol="KOSPI", source="yahoo", as_of=now_utc())
    assert len(rep.train) == 3 and len(rep.test) == 3
    assert rep.primary_horizon_days == 20
    for h in rep.test:
        assert 0.0 <= h.hit_rate <= 1.0
        assert 0.0 <= h.base_rate <= 1.0
        assert h.skill == round(h.hit_rate - h.base_rate, 4)
    assert "1개월" in rep.interpretation
    assert "train" in rep.interpretation  # the verdict now anchors on the train split
