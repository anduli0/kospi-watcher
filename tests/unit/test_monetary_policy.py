"""Unit tests for the BOK monetary-policy signal (ADR-024).

Covers the authoritative config override, the headline auto-classifier, the
MACRO finding override (and NEUTRAL no-op), and the synthesizer tilt.
"""

from __future__ import annotations

from kospi_watcher.domain.agents.schemas import AgentFinding
from kospi_watcher.domain.enums import (
    DataQuality,
    Horizon,
    Impact,
    MarketDirection,
)
from kospi_watcher.domain.prediction.monetary_policy import (
    PolicyStance,
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


def test_config_override_hawkish() -> None:
    s = build_signal(stance_override="hawkish", hikes_override=3)
    assert s.stance is PolicyStance.HAWKISH
    assert s.equity_bias is MarketDirection.BEARISH
    assert s.expected_hikes_2026 == 3
    assert s.source == "config"


def test_config_override_dovish_default_hikes() -> None:
    s = build_signal(stance_override="dovish", hikes_override=0)
    assert s.stance is PolicyStance.DOVISH
    assert s.equity_bias is MarketDirection.BULLISH
    assert s.expected_hikes_2026 < 0


def test_auto_classifies_hawkish_news() -> None:
    s = build_signal(
        stance_override="auto",
        headlines=["한국은행 기준금리 인상 시사", "금통위 추가 인상 전망"],
    )
    assert s.stance is PolicyStance.HAWKISH
    assert s.equity_bias is MarketDirection.BEARISH
    assert s.source == "news"
    assert s.drivers  # picked up the BOK headlines


def test_auto_classifies_dovish_news() -> None:
    s = build_signal(
        stance_override="auto",
        headlines=["한국은행 기준금리 인하 시사", "금통위 금리 인하 가능성"],
    )
    assert s.stance is PolicyStance.DOVISH
    assert s.equity_bias is MarketDirection.BULLISH


def test_auto_neutral_when_no_bok_headlines() -> None:
    s = build_signal(stance_override="auto", headlines=["삼성전자 실적 발표", "코스피 보합"])
    assert s.stance is PolicyStance.NEUTRAL
    assert s.source == "news"


def test_apply_overrides_macro_agents_for_hawkish() -> None:
    findings = [
        _finding("Korea Macro Agent"),
        _finding("Rates and Liquidity Agent"),
        _finding("FX Agent"),
    ]
    s = build_signal(stance_override="hawkish", hikes_override=3)
    out = {f.agent_name: f for f in apply_to_findings(findings, s)}
    assert out["Korea Macro Agent"].direction is MarketDirection.BEARISH
    assert out["Rates and Liquidity Agent"].direction is MarketDirection.BEARISH
    assert out["Rates and Liquidity Agent"].impact is Impact.HIGH
    assert out["FX Agent"].direction is MarketDirection.BULLISH  # untouched


def test_apply_is_noop_when_neutral() -> None:
    findings = [_finding("Korea Macro Agent"), _finding("Rates and Liquidity Agent")]
    s = build_signal(stance_override="neutral")
    assert apply_to_findings(findings, s) == findings


def test_synthesize_tilts_bearish_on_hawkish() -> None:
    s = build_signal(stance_override="hawkish", hikes_override=3)
    pred = synthesize([], monetary_policy=s)
    assert pred.direction is MarketDirection.BEARISH
    assert pred.monetary_policy is not None
    assert pred.monetary_policy.stance is PolicyStance.HAWKISH
    assert "한국은행" in pred.brief


def test_synthesize_unchanged_without_policy() -> None:
    # No monetary_policy → no tilt, no brief clause (backward compatible).
    pred = synthesize([])
    assert pred.monetary_policy is None
    assert "통화정책" not in pred.brief
