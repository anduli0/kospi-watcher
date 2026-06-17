"""Risk-domain schemas: OrderProposal, RiskLimits, RiskCheckResult, RiskDecision.

Monetary fields use :data:`DecimalNoFloat`, so passing a ``float`` raises at
validation time (ADR-008 / spec test #1).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from kospi_watcher.domain.enums import (
    InstrumentType,
    OrderSide,
    OrderType,
    RiskCheckCode,
    RiskDecisionStatus,
)
from kospi_watcher.domain.money import DecimalNoFloat


class OrderProposal(BaseModel):
    """A proposed order produced upstream (strategy/agent). Carries no authority
    to trade — it must pass the Risk Engine before anything else can happen."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    created_at: AwareDatetime
    symbol: str
    instrument_type: InstrumentType
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(gt=0)
    limit_price: DecimalNoFloat | None = None
    reference_price: DecimalNoFloat | None = None
    strategy_id: str
    strategy_version: str
    idempotency_key: str = Field(min_length=1)
    rationale: str | None = None

    @model_validator(mode="after")
    def _require_limit_price(self) -> OrderProposal:
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        return self

    @property
    def effective_price(self) -> Decimal | None:
        """Price used for notional/deviation checks."""
        return self.limit_price if self.limit_price is not None else self.reference_price


class RiskLimits(BaseModel):
    """Operator-controlled limits (loaded from config/risk_limits.yml).

    Empty allow-lists mean *deny everything* — that is the intended default."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    allowed_instruments: frozenset[str] = frozenset()
    allowed_strategies: frozenset[str] = frozenset()
    market_open: bool = False
    max_order_notional: DecimalNoFloat = Decimal("0")
    max_order_quantity: int = 0
    max_position_notional: DecimalNoFloat = Decimal("0")
    max_gross_exposure: DecimalNoFloat = Decimal("0")
    price_deviation_pct: DecimalNoFloat = Decimal("0")
    daily_loss_limit: DecimalNoFloat = Decimal("0")
    max_drawdown_pct: DecimalNoFloat = Decimal("0")
    daily_trade_count: int = 0
    max_open_orders: int = 0
    slippage_limit_pct: DecimalNoFloat = Decimal("0")


class RiskCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: RiskCheckCode
    passed: bool
    detail: str


class RiskDecision(BaseModel):
    """The Risk Engine's verdict. An ApprovedOrder cannot be created unless
    ``status is APPROVED`` (enforced by the ApprovedOrder factory)."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    proposal_id: str
    status: RiskDecisionStatus
    created_at: AwareDatetime
    checks: list[RiskCheckResult] = Field(default_factory=list)
    failed_checks: list[RiskCheckCode] = Field(default_factory=list)
    reason: str
    requires_human: bool = False

    @property
    def approved(self) -> bool:
        return self.status is RiskDecisionStatus.APPROVED
