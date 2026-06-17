"""Paper-trading endpoints: submit orders, list orders/fills, positions, account.

Execution is simulated (PAPER) and gated: in RESEARCH mode submission returns 409.
No real broker is contacted and no real money moves.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.requests import SubmitOrderRequest
from kospi_watcher.api.schemas.responses import (
    AccountResponse,
    FillResponse,
    OrderDetail,
    OrderListResponse,
    OrderResponse,
    PositionResponse,
    SubmitOrderResponse,
)
from kospi_watcher.config import get_settings
from kospi_watcher.db import models, repositories
from kospi_watcher.domain.execution.broker import DuplicateOrderError
from kospi_watcher.domain.execution.position import PositionState
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.marketdata import Quote, get_market_data_provider
from kospi_watcher.trading.service import ExecutionDisabledError, TradingService

router = APIRouter(tags=["trading"])


def _order_response(row: models.OrderRow) -> OrderResponse:
    return OrderResponse(
        id=row.id,
        proposal_id=row.proposal_id,
        risk_decision_id=row.risk_decision_id,
        symbol=row.symbol,
        side=row.side,
        order_type=row.order_type,
        quantity=row.quantity,
        limit_price=row.limit_price,
        status=row.status,
        broker_order_id=row.broker_order_id,
        trading_mode=row.trading_mode,
        filled_quantity=row.filled_quantity,
        avg_fill_price=row.avg_fill_price,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _position_response(row: models.PositionRow, mark: Decimal | None) -> PositionResponse:
    state = PositionState(row.quantity, row.avg_cost, row.realized_pnl)
    return PositionResponse(
        symbol=row.symbol,
        quantity=row.quantity,
        avg_cost=row.avg_cost,
        realized_pnl=row.realized_pnl,
        mark_price=mark,
        market_value=state.market_value(mark) if mark is not None else None,
        unrealized_pnl=state.unrealized_pnl(mark) if mark is not None else None,
    )


@router.post("/orders", response_model=SubmitOrderResponse)
async def submit_order(req: SubmitOrderRequest, session: SessionDep) -> SubmitOrderResponse:
    proposal = req.proposal.to_domain()
    service = TradingService()
    try:
        result = await service.submit_order(
            session,
            proposal,
            trading_mode=get_settings().trading_mode,
            market_open=req.market_open,
            last_price=req.last_price,
        )
    except ExecutionDisabledError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DuplicateOrderError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="duplicate idempotency_key") from exc

    fill = result.fill
    position = result.position
    return SubmitOrderResponse(
        order_id=result.order_id,
        status=result.status.value,
        message=result.message,
        reference_price=result.reference_price,
        decision=result.decision,
        fill=(
            FillResponse(
                id=fill.fill_id,
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=fill.quantity,
                price=fill.price,
                liquidity=fill.liquidity,
                created_at=fill.filled_at,
            )
            if fill is not None
            else None
        ),
        position=(
            PositionResponse(
                symbol=fill.symbol if fill else proposal.symbol,
                quantity=position.quantity,
                avg_cost=position.avg_cost,
                realized_pnl=position.realized_pnl,
                mark_price=result.reference_price,
                market_value=(
                    position.market_value(result.reference_price)
                    if result.reference_price is not None
                    else None
                ),
                unrealized_pnl=(
                    position.unrealized_pnl(result.reference_price)
                    if result.reference_price is not None
                    else None
                ),
            )
            if position is not None
            else None
        ),
    )


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> OrderListResponse:
    rows = await repositories.list_orders(session, limit=limit, offset=offset)
    return OrderListResponse(count=len(rows), orders=[_order_response(r) for r in rows])


@router.get("/orders/{order_id}", response_model=OrderDetail)
async def get_order(order_id: str, session: SessionDep) -> OrderDetail:
    row = await repositories.get_order(session, order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="order not found")
    fills = await repositories.list_fills(session, order_id)
    base = _order_response(row)
    return OrderDetail(
        **base.model_dump(),
        fills=[
            FillResponse(
                id=f.id,
                symbol=f.symbol,
                side=f.side,
                quantity=f.quantity,
                price=f.price,
                liquidity=f.liquidity,
                created_at=f.created_at,
            )
            for f in fills
        ],
    )


async def _marks(symbols: list[str]) -> dict[str, Quote]:
    if not symbols:
        return {}
    return await get_market_data_provider().get_quotes(symbols)


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(session: SessionDep) -> list[PositionResponse]:
    rows = await repositories.list_positions(session)
    marks = await _marks([r.symbol for r in rows])
    return [
        _position_response(r, marks[r.symbol].price if r.symbol in marks else None)
        for r in rows
    ]


@router.get("/account", response_model=AccountResponse)
async def account(session: SessionDep) -> AccountResponse:
    rows = await repositories.list_positions(session)
    marks = await _marks([r.symbol for r in rows])
    positions: list[PositionResponse] = []
    realized = Decimal("0")
    unrealized = Decimal("0")
    gross = Decimal("0")
    for r in rows:
        mark = marks[r.symbol].price if r.symbol in marks else None
        pr = _position_response(r, mark)
        positions.append(pr)
        realized += r.realized_pnl
        if pr.unrealized_pnl is not None:
            unrealized += pr.unrealized_pnl
        if pr.market_value is not None:
            gross += abs(pr.market_value)
    return AccountResponse(
        account="paper",
        as_of=now_utc(),
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        total_pnl=realized + unrealized,
        gross_exposure=gross,
        position_count=len(positions),
        positions=positions,
    )
