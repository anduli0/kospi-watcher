"""Deterministic, deny-by-default Risk Engine (ADR-010)."""

from __future__ import annotations

from decimal import Decimal

from kospi_watcher.domain.enums import (
    InstrumentType,
    OrderSide,
    OrderType,
    RiskCheckCode,
    TradingMode,
)
from kospi_watcher.domain.risk.engine import RiskContext, RiskEngine
from kospi_watcher.domain.risk.limits import load_risk_limits
from kospi_watcher.domain.risk.schemas import OrderProposal, RiskLimits
from kospi_watcher.domain.time import now_utc


def _proposal(**overrides: object) -> OrderProposal:
    base: dict[str, object] = dict(
        proposal_id="p-1",
        created_at=now_utc(),
        symbol="069500",
        instrument_type=InstrumentType.ETF,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=Decimal("35000"),
        strategy_id="baseline-momentum-v0",
        strategy_version="0.1.0",
        idempotency_key="k-1",
    )
    base.update(overrides)
    return OrderProposal(**base)  # type: ignore[arg-type]


def _open_ctx(**overrides: object) -> RiskContext:
    base: dict[str, object] = dict(
        as_of=now_utc(),
        market_open=True,
        last_price=Decimal("35000"),
    )
    base.update(overrides)
    return RiskContext(**base)  # type: ignore[arg-type]


def test_empty_limits_deny_everything() -> None:
    # Empty allow-lists are the deny-by-default posture.
    decision = RiskEngine(RiskLimits()).evaluate(_proposal())
    assert not decision.approved
    assert RiskCheckCode.INSTRUMENT_ALLOWED in decision.failed_checks
    assert RiskCheckCode.STRATEGY_ALLOWED in decision.failed_checks


def test_full_approve_path() -> None:
    decision = RiskEngine(load_risk_limits()).evaluate(_proposal(), _open_ctx())
    assert decision.approved, decision.reason
    assert decision.failed_checks == []
    assert not decision.requires_human  # RESEARCH mode by default


def test_closed_market_is_rejected() -> None:
    decision = RiskEngine(load_risk_limits()).evaluate(
        _proposal(), _open_ctx(market_open=False)
    )
    assert not decision.approved
    assert RiskCheckCode.MARKET_OPEN in decision.failed_checks


def test_missing_quote_is_rejected() -> None:
    decision = RiskEngine(load_risk_limits()).evaluate(
        _proposal(), _open_ctx(last_price=None)
    )
    assert not decision.approved
    assert RiskCheckCode.QUOTE_FRESHNESS in decision.failed_checks


def test_notional_over_limit_is_rejected() -> None:
    # 35,000 * 2,000 = 70,000,000 KRW > 50,000,000 max_order_notional.
    decision = RiskEngine(load_risk_limits()).evaluate(
        _proposal(quantity=2000), _open_ctx()
    )
    assert not decision.approved
    assert RiskCheckCode.MAX_ORDER_NOTIONAL in decision.failed_checks


def test_price_deviation_over_limit_is_rejected() -> None:
    # Limit 35,000 vs last 30,000 = 16.7% deviation > 5% limit.
    decision = RiskEngine(load_risk_limits()).evaluate(
        _proposal(), _open_ctx(last_price=Decimal("30000"))
    )
    assert not decision.approved
    assert RiskCheckCode.PRICE_DEVIATION in decision.failed_checks


def test_duplicate_idempotency_key_is_rejected() -> None:
    ctx = _open_ctx(seen_idempotency_keys=frozenset({"k-1"}))
    decision = RiskEngine(load_risk_limits()).evaluate(_proposal(), ctx)
    assert not decision.approved
    assert RiskCheckCode.DUPLICATE_ORDER in decision.failed_checks


def test_guarded_live_defers_to_human() -> None:
    ctx = _open_ctx(trading_mode=TradingMode.GUARDED_LIVE)
    decision = RiskEngine(load_risk_limits()).evaluate(_proposal(), ctx)
    assert decision.approved
    assert decision.requires_human  # never auto-sends in GUARDED_LIVE
