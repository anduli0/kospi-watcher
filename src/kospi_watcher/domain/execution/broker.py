"""Broker abstraction, ApprovedOrder factory, and a safe mock adapter.

``ApprovedOrder`` is the only object the Execution Gateway will submit, and it
can only be created from an APPROVED ``RiskDecision``. The ``MockBrokerAdapter``
performs NO real orders and rejects duplicate idempotency keys.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.enums import OrderSide, OrderStatus, OrderType, RiskDecisionStatus
from kospi_watcher.domain.money import DecimalNoFloat
from kospi_watcher.domain.risk.schemas import OrderProposal, RiskDecision
from kospi_watcher.domain.time import now_utc

MOCK_BROKER_BANNER = "MOCK BROKER — NO REAL ORDERS, NOT REAL MARKET DATA"


class ApprovedOrderError(RuntimeError):
    """Raised when an ApprovedOrder is constructed without a valid approval."""


class DuplicateOrderError(RuntimeError):
    """Raised when an order with a previously-seen idempotency key is submitted."""


class ApprovedOrder(BaseModel):
    """An order authorised for submission. Construct via :meth:`from_decision`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: str
    proposal_id: str
    risk_decision_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(gt=0)
    limit_price: DecimalNoFloat | None = None
    idempotency_key: str = Field(min_length=1)
    approved_at: AwareDatetime

    @classmethod
    def from_decision(
        cls,
        proposal: OrderProposal,
        decision: RiskDecision,
        *,
        order_id: str | None = None,
    ) -> ApprovedOrder:
        """Create an ApprovedOrder — only if ``decision`` APPROVED ``proposal``."""
        if decision.status is not RiskDecisionStatus.APPROVED:
            raise ApprovedOrderError(
                "cannot create an ApprovedOrder without an APPROVED RiskDecision "
                f"(status={decision.status})"
            )
        if decision.proposal_id != proposal.proposal_id:
            raise ApprovedOrderError("RiskDecision does not belong to this proposal")
        return cls(
            order_id=order_id or uuid.uuid4().hex,
            proposal_id=proposal.proposal_id,
            risk_decision_id=decision.decision_id,
            symbol=proposal.symbol,
            side=proposal.side,
            order_type=proposal.order_type,
            quantity=proposal.quantity,
            limit_price=proposal.limit_price,
            idempotency_key=proposal.idempotency_key,
            approved_at=now_utc(),
        )


class BrokerOrder(BaseModel):
    """A broker's acknowledgement of a submitted order."""

    model_config = ConfigDict(extra="forbid")

    broker_order_id: str
    status: OrderStatus
    idempotency_key: str
    accepted_at: AwareDatetime


@runtime_checkable
class BrokerAdapter(Protocol):
    """Broker-agnostic interface (spec §10). Real KIS/Kiwoom adapters implement
    this later; only the Execution Gateway is allowed to call ``submit_order``."""

    async def submit_order(self, order: ApprovedOrder) -> BrokerOrder: ...
    async def cancel_order(self, broker_order_id: str) -> None: ...


class MockBrokerAdapter:
    """A safe, in-memory broker. Never contacts a real broker; enforces
    idempotency so the same key cannot be submitted twice."""

    mode = "MOCK"

    def __init__(self) -> None:
        self._submitted: dict[str, BrokerOrder] = {}

    async def submit_order(self, order: ApprovedOrder) -> BrokerOrder:
        if order.idempotency_key in self._submitted:
            raise DuplicateOrderError(
                f"duplicate idempotency_key: {order.idempotency_key}"
            )
        broker_order = BrokerOrder(
            broker_order_id=f"MOCK-{uuid.uuid4().hex[:12]}",
            status=OrderStatus.SUBMITTED,
            idempotency_key=order.idempotency_key,
            accepted_at=now_utc(),
        )
        self._submitted[order.idempotency_key] = broker_order
        return broker_order

    async def cancel_order(self, broker_order_id: str) -> None:
        # Mock: no-op. A real adapter would call the broker's cancel API.
        return None
