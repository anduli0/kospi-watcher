"""Paper broker: SUBMITTED ack, idempotency, fill pricing."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kospi_watcher.domain.enums import OrderSide, OrderStatus, OrderType
from kospi_watcher.domain.execution.broker import ApprovedOrder, DuplicateOrderError
from kospi_watcher.domain.execution.paper import PaperBrokerAdapter, PaperFillError
from kospi_watcher.domain.time import now_utc


def _approved(
    *, order_type: OrderType = OrderType.LIMIT, limit: Decimal | None = Decimal("35000"),
    key: str = "k1",
) -> ApprovedOrder:
    return ApprovedOrder(
        order_id="o1",
        proposal_id="p1",
        risk_decision_id="d1",
        symbol="069500",
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=10,
        limit_price=limit,
        idempotency_key=key,
        approved_at=now_utc(),
    )


async def test_submit_acks_and_rejects_duplicate() -> None:
    broker = PaperBrokerAdapter()
    assert broker.mode == "PAPER"
    ack = await broker.submit_order(_approved())
    assert ack.status is OrderStatus.SUBMITTED
    assert ack.broker_order_id.startswith("PAPER-")
    with pytest.raises(DuplicateOrderError):
        await broker.submit_order(_approved())


def test_limit_order_fills_at_limit() -> None:
    fill = PaperBrokerAdapter().simulate_fill(_approved(), Decimal("99999"))
    assert fill.price == Decimal("35000")
    assert fill.quantity == 10
    assert fill.liquidity == "PAPER"


def test_market_order_fills_at_reference() -> None:
    order = _approved(order_type=OrderType.MARKET, limit=None)
    fill = PaperBrokerAdapter().simulate_fill(order, Decimal("40000"))
    assert fill.price == Decimal("40000")


def test_market_order_without_reference_raises() -> None:
    order = _approved(order_type=OrderType.MARKET, limit=None)
    with pytest.raises(PaperFillError):
        PaperBrokerAdapter().simulate_fill(order, None)
