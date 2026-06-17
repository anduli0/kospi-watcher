"""Paper (simulated) broker — the safe execution backend.

A ``PaperBrokerAdapter`` accepts an :class:`ApprovedOrder` and produces a
deterministic full fill. It NEVER contacts a real broker and moves NO real
money, so it is the legitimate execution path while live trading remains
unimplemented. Duplicate idempotency keys are rejected, exactly like the mock.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.enums import OrderSide, OrderStatus, OrderType
from kospi_watcher.domain.execution.broker import (
    ApprovedOrder,
    BrokerOrder,
    DuplicateOrderError,
)
from kospi_watcher.domain.money import DecimalNoFloat
from kospi_watcher.domain.time import now_utc

PAPER_BROKER_BANNER = "PAPER BROKER — SIMULATED FILLS, NO REAL ORDERS, NO REAL MONEY"


class Fill(BaseModel):
    """A simulated execution against a paper order."""

    model_config = ConfigDict(extra="forbid")

    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    price: DecimalNoFloat
    liquidity: str = "PAPER"
    filled_at: AwareDatetime


class PaperFillError(RuntimeError):
    """Raised when a paper fill cannot be priced (no limit and no reference)."""


class PaperBrokerAdapter:
    """In-memory simulated broker. ``mode == "PAPER"``."""

    mode = "PAPER"

    def __init__(self) -> None:
        self._submitted: dict[str, BrokerOrder] = {}

    async def submit_order(self, order: ApprovedOrder) -> BrokerOrder:
        if order.idempotency_key in self._submitted:
            raise DuplicateOrderError(
                f"duplicate idempotency_key: {order.idempotency_key}"
            )
        ack = BrokerOrder(
            broker_order_id=f"PAPER-{uuid.uuid4().hex[:12]}",
            status=OrderStatus.SUBMITTED,
            idempotency_key=order.idempotency_key,
            accepted_at=now_utc(),
        )
        self._submitted[order.idempotency_key] = ack
        return ack

    async def cancel_order(self, broker_order_id: str) -> None:
        return None

    def simulate_fill(
        self, order: ApprovedOrder, reference_price: Decimal | None
    ) -> Fill:
        """Fully fill ``order`` at its limit price (LIMIT) or the reference
        price (MARKET). Raises if a market order has no reference price."""
        if order.order_type is OrderType.LIMIT and order.limit_price is not None:
            fill_price = order.limit_price
        elif reference_price is not None:
            fill_price = reference_price
        else:
            raise PaperFillError(
                f"cannot price a MARKET fill for {order.symbol} without a reference price"
            )
        return Fill(
            fill_id=uuid.uuid4().hex,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            filled_at=now_utc(),
        )
