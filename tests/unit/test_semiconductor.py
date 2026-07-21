"""Unit tests for the semiconductor mega-cap cycle signal (ADR-031).

Covers the authoritative config override, the leader-momentum auto classifier,
the Technology and Semiconductor finding override (and NEUTRAL no-op), and the
synthesizer tilt + brief clause.
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
from kospi_watcher.domain.prediction.semiconductor import (
    MOM_WINDOW,
    SemiCycleStance,
    apply_to_findings,
    build_signal,
)
from kospi_watcher.domain.prediction.synthesizer import synthesize
from kospi_watcher.domain.time import now_utc


def _finding(name: str, direction: MarketDirection = MarketDirection.BULLISH) -> AgentFinding:
    t = now_utc()
    return AgentFinding(
        agent_name=name, agent_version="0", as_of=t, horizon=Horizon.D5,
        direction=direction, impact=Impact.MEDIUM, confidence=0.5, thesis="x",
        data_quality=DataQuality.OK, model_name="mock", prompt_version="0", created_at=t,
    )


def _series(start: float, pct_over_window: float) -> list[Decimal]:
    """A close series where the last close is ``pct_over_window`` vs MOM_WINDOW ago."""
    n = MOM_WINDOW + 5
    end = start * (1.0 + pct_over_window)
    step = (end - start) / (n - 1)
    return [Decimal(str(round(start + step * i, 2))) for i in range(n)]


def test_config_override_downcycle() -> None:
    s = build_signal(stance_override="downcycle")
    assert s.stance is SemiCycleStance.DOWNCYCLE
    assert s.equity_bias is MarketDirection.BEARISH
    assert s.source == "config"


def test_config_override_expansion() -> None:
    s = build_signal(stance_override="expansion")
    assert s.stance is SemiCycleStance.EXPANSION
    assert s.equity_bias is MarketDirection.BULLISH


def test_auto_downcycle_on_falling_leaders() -> None:
    s = build_signal(
        stance_override="auto",
        samsung_closes=_series(80000, -0.20),
        hynix_closes=_series(200000, -0.15),
    )
    assert s.stance is SemiCycleStance.DOWNCYCLE
    assert s.equity_bias is MarketDirection.BEARISH
    assert s.source == "price"
    assert s.blended_mom_pct is not None and s.blended_mom_pct < 0


def test_auto_expansion_on_rising_leaders() -> None:
    s = build_signal(
        stance_override="auto",
        samsung_closes=_series(60000, 0.15),
        hynix_closes=_series(150000, 0.20),
    )
    assert s.stance is SemiCycleStance.EXPANSION
    assert s.equity_bias is MarketDirection.BULLISH


def test_auto_neutral_when_flat() -> None:
    s = build_signal(
        stance_override="auto",
        samsung_closes=_series(70000, 0.01),
        hynix_closes=_series(180000, -0.01),
    )
    assert s.stance is SemiCycleStance.NEUTRAL


def test_auto_neutral_when_no_history() -> None:
    s = build_signal(stance_override="auto", samsung_closes=[], hynix_closes=[])
    assert s.stance is SemiCycleStance.NEUTRAL
    assert s.source == "mock"


def test_apply_overrides_semi_agent_on_downcycle() -> None:
    findings = [
        _finding("Technology and Semiconductor Agent"),
        _finding("Earnings and Valuation Agent"),
    ]
    s = build_signal(stance_override="downcycle")
    out = {f.agent_name: f for f in apply_to_findings(findings, s)}
    assert out["Technology and Semiconductor Agent"].direction is MarketDirection.BEARISH
    assert out["Earnings and Valuation Agent"].direction is MarketDirection.BULLISH  # untouched


def test_apply_is_noop_when_neutral() -> None:
    findings = [_finding("Technology and Semiconductor Agent")]
    s = build_signal(stance_override="neutral")
    assert apply_to_findings(findings, s) == findings


def test_synthesize_tilts_bearish_on_downcycle() -> None:
    s = build_signal(stance_override="downcycle")
    pred = synthesize([], semiconductor=s)
    assert pred.direction is MarketDirection.BEARISH
    assert pred.semiconductor is not None
    assert pred.semiconductor.stance is SemiCycleStance.DOWNCYCLE
    assert "반도체" in pred.brief


def test_synthesize_unchanged_without_semiconductor() -> None:
    pred = synthesize([])
    assert pred.semiconductor is None
    assert "메모리 사이클" not in pred.brief
