"""API request models.

Price fields are typed ``Decimal`` (lenient at the boundary: JSON numbers are
coerced). When converted to the domain ``OrderProposal`` they pass through
``DecimalNoFloat``, so no ``float`` ever reaches the domain money path.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kospi_watcher.domain.enums import InstrumentType, OrderSide, OrderType
from kospi_watcher.domain.risk.schemas import OrderProposal
from kospi_watcher.domain.time import now_utc


class MockRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str
    universe: list[str] = Field(default_factory=list)


class OrderProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    instrument_type: InstrumentType
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(gt=0)
    limit_price: Decimal | None = None
    reference_price: Decimal | None = None
    strategy_id: str
    strategy_version: str = "0.1.0"
    idempotency_key: str = Field(min_length=1)
    rationale: str | None = None

    @model_validator(mode="after")
    def _require_limit_price(self) -> OrderProposalRequest:
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        return self

    def to_domain(self) -> OrderProposal:
        return OrderProposal(
            proposal_id=uuid.uuid4().hex,
            created_at=now_utc(),
            symbol=self.symbol,
            instrument_type=self.instrument_type,
            side=self.side,
            order_type=self.order_type,
            quantity=self.quantity,
            limit_price=self.limit_price,
            reference_price=self.reference_price,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            idempotency_key=self.idempotency_key,
            rationale=self.rationale,
        )


class RiskEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: OrderProposalRequest
    market_open: bool = True
    last_price: Decimal | None = None
    position_notional: Decimal = Decimal("0")
    gross_exposure: Decimal = Decimal("0")
    daily_realized_loss: Decimal = Decimal("0")
    open_orders: int = 0
    daily_trade_count: int = 0


class SubmitOrderRequest(BaseModel):
    """Submit a proposal for paper execution (risk-gated, simulated fill)."""

    model_config = ConfigDict(extra="forbid")

    proposal: OrderProposalRequest
    market_open: bool = True
    last_price: Decimal | None = None
