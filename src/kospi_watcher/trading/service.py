"""The paper-trading orchestrator.

``TradingService.submit_order`` is the one place that takes an
:class:`OrderProposal` all the way to a (simulated) fill. It runs the
deterministic Risk Engine, walks the order through the 13-state machine
(persisting and audit-logging each transition), submits through the
:class:`ExecutionGateway` to the :class:`PaperBrokerAdapter`, simulates a fill,
and updates the position / realized PnL.

It refuses to execute unless ``TRADING_MODE=PAPER`` — RESEARCH is analysis only,
and the live modes are blocked because live execution is not implemented.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.db import models, repositories
from kospi_watcher.domain.enums import AuditAction, OrderStatus, TradingMode
from kospi_watcher.domain.execution.broker import ApprovedOrder, DuplicateOrderError
from kospi_watcher.domain.execution.order_state import OrderStateMachine
from kospi_watcher.domain.execution.paper import Fill, PaperBrokerAdapter
from kospi_watcher.domain.execution.position import PositionState, apply_fill
from kospi_watcher.domain.risk.engine import RiskContext, RiskEngine
from kospi_watcher.domain.risk.limits import load_risk_limits
from kospi_watcher.domain.risk.schemas import OrderProposal, RiskDecision
from kospi_watcher.domain.time import now_utc
from kospi_watcher.execution_gateway.gateway import ExecutionGateway
from kospi_watcher.infrastructure.marketdata import get_market_data_provider

_ALLOWED_EXECUTION_MODES = frozenset({TradingMode.PAPER})


class ExecutionDisabledError(RuntimeError):
    """Raised when order execution is attempted in a non-PAPER trading mode."""


@dataclass(frozen=True)
class SubmitResult:
    order_id: str
    status: OrderStatus
    decision: RiskDecision
    fill: Fill | None
    position: PositionState | None
    reference_price: Decimal | None
    message: str


class TradingService:
    def __init__(
        self,
        *,
        broker: PaperBrokerAdapter | None = None,
        gateway: ExecutionGateway | None = None,
    ) -> None:
        self._broker = broker or PaperBrokerAdapter()
        self._gateway = gateway or ExecutionGateway(self._broker)

    async def submit_order(
        self,
        session: AsyncSession,
        proposal: OrderProposal,
        *,
        trading_mode: TradingMode,
        market_open: bool = True,
        last_price: Decimal | None = None,
    ) -> SubmitResult:
        if trading_mode not in _ALLOWED_EXECUTION_MODES:
            raise ExecutionDisabledError(
                f"order execution is disabled in {trading_mode.value} mode "
                "(set TRADING_MODE=PAPER to enable simulated trading)"
            )
        if await repositories.order_exists(session, proposal.idempotency_key):
            raise DuplicateOrderError(
                f"duplicate idempotency_key: {proposal.idempotency_key}"
            )

        reference_price = await self._reference_price(proposal, last_price)
        # Enrich a MARKET proposal with the live reference price so the Risk
        # Engine can size it (it prices off the proposal's effective_price).
        if proposal.reference_price is None and reference_price is not None:
            proposal = proposal.model_copy(update={"reference_price": reference_price})
        decision = await self._evaluate_risk(
            session, proposal, trading_mode, market_open, reference_price
        )

        now = now_utc()
        order = models.OrderRow(
            id=uuid.uuid4().hex,
            proposal_id=proposal.proposal_id,
            risk_decision_id=decision.decision_id,
            symbol=proposal.symbol,
            instrument_type=proposal.instrument_type.value,
            side=proposal.side.value,
            order_type=proposal.order_type.value,
            quantity=proposal.quantity,
            limit_price=proposal.limit_price,
            status=OrderStatus.PROPOSED.value,
            broker_order_id=None,
            idempotency_key=proposal.idempotency_key,
            trading_mode=trading_mode.value,
            filled_quantity=0,
            avg_fill_price=None,
            created_at=now,
            updated_at=now,
        )
        session.add(order)
        sm = OrderStateMachine()  # PROPOSED

        if not decision.approved:
            self._advance(order, sm, OrderStatus.RISK_REJECTED)
            await self._audit(session, order, f"risk rejected: {decision.reason}")
            await session.commit()
            return SubmitResult(
                order.id, OrderStatus.RISK_REJECTED, decision, None, None,
                reference_price, "rejected by risk engine",
            )

        approved = ApprovedOrder.from_decision(proposal, decision, order_id=order.id)
        self._advance(order, sm, OrderStatus.RISK_APPROVED)
        self._advance(order, sm, OrderStatus.APPROVED)
        self._advance(order, sm, OrderStatus.SUBMITTING)
        ack = await self._gateway.submit(approved)
        order.broker_order_id = ack.broker_order_id
        self._advance(order, sm, OrderStatus.SUBMITTED)

        fill = self._broker.simulate_fill(approved, reference_price)
        session.add(
            models.FillRow(
                id=fill.fill_id,
                order_id=order.id,
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=fill.quantity,
                price=fill.price,
                liquidity=fill.liquidity,
                created_at=fill.filled_at,
            )
        )
        self._advance(order, sm, OrderStatus.FILLED)
        order.filled_quantity = fill.quantity
        order.avg_fill_price = fill.price

        new_state = await self._apply_to_position(session, fill)
        await self._audit(
            session,
            order,
            f"paper FILLED {fill.side.value} {fill.quantity} {fill.symbol} @ {fill.price}",
        )
        await session.commit()
        return SubmitResult(
            order.id, OrderStatus.FILLED, decision, fill, new_state,
            reference_price, "filled (paper)",
        )

    # --- helpers ---

    @staticmethod
    async def _reference_price(
        proposal: OrderProposal, last_price: Decimal | None
    ) -> Decimal | None:
        if last_price is not None:
            return last_price
        quote = await get_market_data_provider().get_quote(proposal.symbol)
        return quote.price if quote is not None else proposal.effective_price

    @staticmethod
    async def _evaluate_risk(
        session: AsyncSession,
        proposal: OrderProposal,
        trading_mode: TradingMode,
        market_open: bool,
        reference_price: Decimal | None,
    ) -> RiskDecision:
        positions = await repositories.list_positions(session)
        gross = sum(
            (abs(p.quantity) * p.avg_cost for p in positions), start=Decimal("0")
        )
        existing = next((p for p in positions if p.symbol == proposal.symbol), None)
        mark = reference_price if reference_price is not None else Decimal("0")
        position_notional = abs(existing.quantity) * mark if existing else Decimal("0")

        decision = RiskEngine(load_risk_limits()).evaluate(
            proposal,
            RiskContext(
                as_of=now_utc(),
                trading_mode=trading_mode,
                market_open=market_open,
                last_price=reference_price,
                position_notional=position_notional,
                gross_exposure=gross,
            ),
        )
        await repositories.save_risk_decision(session, decision)
        return decision

    @staticmethod
    def _advance(order: models.OrderRow, sm: OrderStateMachine, to: OrderStatus) -> None:
        sm.transition(to)  # raises on an illegal transition
        order.status = to.value
        order.updated_at = now_utc()

    @staticmethod
    async def _apply_to_position(session: AsyncSession, fill: Fill) -> PositionState:
        row = await repositories.get_position_row(session, fill.symbol)
        prev = (
            PositionState(row.quantity, row.avg_cost, row.realized_pnl)
            if row is not None
            else PositionState()
        )
        new_state = apply_fill(prev, fill.side, fill.quantity, fill.price)
        if row is not None:
            row.quantity = new_state.quantity
            row.avg_cost = new_state.avg_cost
            row.realized_pnl = new_state.realized_pnl
            row.updated_at = now_utc()
        else:
            session.add(
                models.PositionRow(
                    account="paper",
                    symbol=fill.symbol,
                    quantity=new_state.quantity,
                    avg_cost=new_state.avg_cost,
                    realized_pnl=new_state.realized_pnl,
                    updated_at=now_utc(),
                )
            )
        return new_state

    @staticmethod
    async def _audit(session: AsyncSession, order: models.OrderRow, summary: str) -> None:
        await repositories.add_audit_log(
            session,
            action=AuditAction.ORDER_STATE_TRANSITION,
            entity_type="order",
            entity_id=order.id,
            summary=summary,
            payload={"status": order.status, "symbol": order.symbol},
        )
