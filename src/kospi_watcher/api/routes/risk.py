"""POST /api/v1/risk/evaluate — run the deterministic deny-by-default Risk Engine.

No order is placed; this only produces and persists a RiskDecision."""

from __future__ import annotations

from fastapi import APIRouter

from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.requests import RiskEvaluateRequest
from kospi_watcher.config import get_settings
from kospi_watcher.db.repositories import add_audit_log, save_risk_decision
from kospi_watcher.domain.enums import AuditAction
from kospi_watcher.domain.risk.engine import RiskContext, RiskEngine
from kospi_watcher.domain.risk.limits import load_risk_limits
from kospi_watcher.domain.risk.schemas import RiskDecision
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.marketdata import get_market_data_provider

router = APIRouter(tags=["risk"])


@router.post("/risk/evaluate", response_model=RiskDecision)
async def evaluate(req: RiskEvaluateRequest, session: SessionDep) -> RiskDecision:
    proposal = req.proposal.to_domain()
    engine = RiskEngine(load_risk_limits())
    # Prefer an explicit last_price; otherwise use a live quote; finally fall
    # back to the proposal's own price so the deviation check still runs.
    last_price = req.last_price
    if last_price is None:
        quote = await get_market_data_provider().get_quote(proposal.symbol)
        last_price = quote.price if quote is not None else proposal.effective_price
    ctx = RiskContext(
        as_of=now_utc(),
        trading_mode=get_settings().trading_mode,
        market_open=req.market_open,
        last_price=last_price,
        position_notional=req.position_notional,
        gross_exposure=req.gross_exposure,
        daily_realized_loss=req.daily_realized_loss,
        open_orders=req.open_orders,
        daily_trade_count=req.daily_trade_count,
    )
    decision = engine.evaluate(proposal, ctx)

    await save_risk_decision(session, decision)
    await add_audit_log(
        session,
        action=AuditAction.RISK_EVALUATED,
        entity_type="risk_decision",
        entity_id=decision.decision_id,
        summary=f"risk {decision.status.value} for {proposal.symbol}",
        payload={
            "status": decision.status.value,
            "failed_checks": [c.value for c in decision.failed_checks],
        },
    )
    await session.commit()
    return decision
