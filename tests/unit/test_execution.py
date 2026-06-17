"""Execution boundary: ApprovedOrder factory, mock broker, gateway isolation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kospi_watcher.domain.enums import (
    InstrumentType,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecisionStatus,
)
from kospi_watcher.domain.execution.broker import (
    ApprovedOrder,
    ApprovedOrderError,
    BrokerOrder,
    DuplicateOrderError,
    MockBrokerAdapter,
)
from kospi_watcher.domain.risk.engine import RiskContext, RiskEngine
from kospi_watcher.domain.risk.limits import load_risk_limits
from kospi_watcher.domain.risk.schemas import OrderProposal, RiskDecision
from kospi_watcher.domain.time import now_utc
from kospi_watcher.execution_gateway.gateway import (
    ExecutionGateway,
    GatewayBlockedError,
)


def _proposal(idempotency_key: str = "k-1") -> OrderProposal:
    return OrderProposal(
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
        idempotency_key=idempotency_key,
    )


def _approved_decision(proposal: OrderProposal) -> RiskDecision:
    ctx = RiskContext(as_of=now_utc(), market_open=True, last_price=Decimal("35000"))
    decision = RiskEngine(load_risk_limits()).evaluate(proposal, ctx)
    assert decision.approved
    return decision


def test_approved_order_only_from_approved_decision() -> None:
    proposal = _proposal()
    order = ApprovedOrder.from_decision(proposal, _approved_decision(proposal))
    assert order.symbol == "069500"
    assert order.idempotency_key == "k-1"


def test_approved_order_rejects_rejected_decision() -> None:
    proposal = _proposal()
    rejected = RiskDecision(
        decision_id="d-1",
        proposal_id=proposal.proposal_id,
        status=RiskDecisionStatus.REJECTED,
        created_at=now_utc(),
        reason="nope",
    )
    with pytest.raises(ApprovedOrderError):
        ApprovedOrder.from_decision(proposal, rejected)


def test_approved_order_rejects_mismatched_proposal() -> None:
    proposal = _proposal()
    decision = _approved_decision(proposal)  # bound to proposal_id "p-1"
    other = proposal.model_copy(update={"proposal_id": "p-different"})
    with pytest.raises(ApprovedOrderError):
        ApprovedOrder.from_decision(other, decision)


async def test_mock_broker_submits_and_rejects_duplicates() -> None:
    proposal = _proposal()
    order = ApprovedOrder.from_decision(proposal, _approved_decision(proposal))
    broker = MockBrokerAdapter()
    ack = await broker.submit_order(order)
    assert isinstance(ack, BrokerOrder)
    assert ack.status is OrderStatus.SUBMITTED
    assert ack.broker_order_id.startswith("MOCK-")
    with pytest.raises(DuplicateOrderError):
        await broker.submit_order(order)


async def test_gateway_allows_mock_submission() -> None:
    proposal = _proposal()
    order = ApprovedOrder.from_decision(proposal, _approved_decision(proposal))
    gateway = ExecutionGateway()  # default mock broker
    assert gateway.broker_mode == "MOCK"
    ack = await gateway.submit(order)
    assert ack.status is OrderStatus.SUBMITTED


async def test_gateway_blocks_non_mock_while_live_disabled() -> None:
    class _FakeLiveBroker:
        mode = "LIVE"

        async def submit_order(self, order: ApprovedOrder) -> BrokerOrder:
            raise AssertionError("must never be reached while live is disabled")

        async def cancel_order(self, broker_order_id: str) -> None:
            return None

    proposal = _proposal()
    order = ApprovedOrder.from_decision(proposal, _approved_decision(proposal))
    gateway = ExecutionGateway(broker=_FakeLiveBroker())
    with pytest.raises(GatewayBlockedError):
        await gateway.submit(order)
