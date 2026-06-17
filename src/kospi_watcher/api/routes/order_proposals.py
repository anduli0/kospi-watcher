"""POST /api/v1/order-proposals/validate — schema-validate and persist a proposal.

No order is placed. Duplicate idempotency keys are rejected with 409."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.requests import OrderProposalRequest
from kospi_watcher.api.schemas.responses import ValidationResponse
from kospi_watcher.db.repositories import add_audit_log, save_proposal
from kospi_watcher.domain.enums import AuditAction

router = APIRouter(tags=["order-proposals"])


@router.post("/order-proposals/validate", response_model=ValidationResponse)
async def validate_proposal(
    req: OrderProposalRequest, session: SessionDep
) -> ValidationResponse:
    proposal = req.to_domain()
    try:
        await save_proposal(session, proposal)
        await add_audit_log(
            session,
            action=AuditAction.ORDER_PROPOSAL_VALIDATED,
            entity_type="order_proposal",
            entity_id=proposal.proposal_id,
            summary=(
                f"validated proposal {proposal.side.value} "
                f"{proposal.quantity} {proposal.symbol}"
            ),
            payload={"symbol": proposal.symbol, "strategy": proposal.strategy_id},
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="duplicate idempotency_key"
        ) from exc

    return ValidationResponse(
        valid=True,
        proposal_id=proposal.proposal_id,
        detail="schema valid; persisted as PROPOSED; no order placed",
    )
