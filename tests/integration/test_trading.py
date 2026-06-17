"""End-to-end paper trading through TradingService (DB-backed)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.db import repositories
from kospi_watcher.domain.enums import (
    InstrumentType,
    OrderSide,
    OrderStatus,
    OrderType,
    TradingMode,
)
from kospi_watcher.domain.execution.broker import DuplicateOrderError
from kospi_watcher.domain.risk.schemas import OrderProposal
from kospi_watcher.domain.time import now_utc
from kospi_watcher.trading.service import ExecutionDisabledError, TradingService


def _proposal(
    key: str,
    *,
    side: OrderSide = OrderSide.BUY,
    qty: int = 10,
    limit: Decimal = Decimal("35000"),
) -> OrderProposal:
    return OrderProposal(
        proposal_id=f"p-{key}",
        created_at=now_utc(),
        symbol="069500",
        instrument_type=InstrumentType.ETF,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=qty,
        limit_price=limit,
        strategy_id="baseline-momentum-v0",
        strategy_version="0.1.0",
        idempotency_key=key,
    )


async def test_paper_buy_fills_and_creates_position(session: AsyncSession) -> None:
    result = await TradingService().submit_order(
        session, _proposal("buy1"),
        trading_mode=TradingMode.PAPER, market_open=True, last_price=Decimal("35000"),
    )
    assert result.status is OrderStatus.FILLED
    assert result.fill is not None and result.fill.price == Decimal("35000")
    assert result.position is not None and result.position.quantity == 10
    assert result.position.avg_cost == Decimal("35000")

    orders = await repositories.list_orders(session)
    assert len(orders) == 1
    assert orders[0].status == "FILLED" and orders[0].filled_quantity == 10
    assert orders[0].broker_order_id is not None

    pos = await repositories.get_position_row(session, "069500")
    assert pos is not None and pos.quantity == 10


async def test_research_mode_refuses_execution(session: AsyncSession) -> None:
    with pytest.raises(ExecutionDisabledError):
        await TradingService().submit_order(
            session, _proposal("r1"), trading_mode=TradingMode.RESEARCH
        )


async def test_risk_rejected_order_is_not_filled(session: AsyncSession) -> None:
    result = await TradingService().submit_order(
        session, _proposal("rej1"),
        trading_mode=TradingMode.PAPER, market_open=False, last_price=Decimal("35000"),
    )
    assert result.status is OrderStatus.RISK_REJECTED
    assert result.fill is None
    assert (await repositories.list_orders(session))[0].status == "RISK_REJECTED"
    assert await repositories.get_position_row(session, "069500") is None


async def test_duplicate_idempotency_key_rejected(session: AsyncSession) -> None:
    await TradingService().submit_order(
        session, _proposal("dup"),
        trading_mode=TradingMode.PAPER, market_open=True, last_price=Decimal("35000"),
    )
    with pytest.raises(DuplicateOrderError):
        await TradingService().submit_order(
            session, _proposal("dup"),
            trading_mode=TradingMode.PAPER, market_open=True, last_price=Decimal("35000"),
        )


async def test_sell_realizes_pnl(session: AsyncSession) -> None:
    svc = TradingService()
    await svc.submit_order(
        session, _proposal("b"),
        trading_mode=TradingMode.PAPER, market_open=True, last_price=Decimal("35000"),
    )
    result = await svc.submit_order(
        session, _proposal("s", side=OrderSide.SELL, qty=4, limit=Decimal("36000")),
        trading_mode=TradingMode.PAPER, market_open=True, last_price=Decimal("36000"),
    )
    assert result.status is OrderStatus.FILLED
    assert result.position is not None
    assert result.position.quantity == 6
    assert result.position.realized_pnl == Decimal("4000")  # 4 * (36000 - 35000)
