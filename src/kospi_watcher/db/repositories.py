"""Thin async repositories over the ORM models.

These wrap the few persistence operations the Phase-1 API needs. The audit-log
helper only ever *inserts* (append-only, ADR-006).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.db import models
from kospi_watcher.domain.agents.schemas import AgentRun
from kospi_watcher.domain.enums import AuditAction
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.risk.schemas import OrderProposal, RiskDecision
from kospi_watcher.domain.time import now_utc


async def add_audit_log(
    session: AsyncSession,
    *,
    action: AuditAction,
    entity_type: str,
    summary: str,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> models.AuditLogRow:
    """Append one audit-log row. Callers must pass only non-sensitive payloads."""
    row = models.AuditLogRow(
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        payload=payload,
        created_at=now_utc(),
    )
    session.add(row)
    await session.flush()
    return row


async def save_agent_run(session: AsyncSession, run: AgentRun) -> models.AgentRunRow:
    """Persist an AgentRun and its findings."""
    row = models.AgentRunRow(
        id=run.run_id,
        agent_name=run.agent_name,
        agent_version=run.agent_version,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        model_name=run.model_name,
        prompt_version=run.prompt_version,
        error=run.error,
        created_at=now_utc(),
    )
    session.add(row)
    for finding in run.findings:
        session.add(
            models.AgentFindingRow(
                id=uuid.uuid4().hex,
                run_id=run.run_id,
                agent_name=finding.agent_name,
                agent_version=finding.agent_version,
                schema_version=finding.schema_version,
                as_of=finding.as_of,
                horizon=finding.horizon.value,
                direction=finding.direction.value,
                impact=finding.impact.value,
                confidence=finding.confidence,
                thesis=finding.thesis,
                evidence=[e.model_dump(mode="json") for e in finding.evidence],
                counterevidence=[e.model_dump(mode="json") for e in finding.counterevidence],
                affected_sectors=finding.affected_sectors,
                affected_symbols=finding.affected_symbols,
                invalidation_conditions=finding.invalidation_conditions,
                data_quality=finding.data_quality.value,
                model_name=finding.model_name,
                prompt_version=finding.prompt_version,
                created_at=finding.created_at,
            )
        )
    await session.flush()
    return row


async def save_proposal(
    session: AsyncSession, proposal: OrderProposal, *, status: str = "PROPOSED"
) -> models.OrderProposalRow:
    row = models.OrderProposalRow(
        id=proposal.proposal_id,
        symbol=proposal.symbol,
        instrument_type=proposal.instrument_type.value,
        side=proposal.side.value,
        order_type=proposal.order_type.value,
        quantity=proposal.quantity,
        limit_price=proposal.limit_price,
        reference_price=proposal.reference_price,
        strategy_id=proposal.strategy_id,
        strategy_version=proposal.strategy_version,
        idempotency_key=proposal.idempotency_key,
        rationale=proposal.rationale,
        status=status,
        created_at=now_utc(),
    )
    session.add(row)
    await session.flush()
    return row


async def save_risk_decision(
    session: AsyncSession, decision: RiskDecision
) -> models.RiskDecisionRow:
    row = models.RiskDecisionRow(
        id=decision.decision_id,
        proposal_id=decision.proposal_id,
        status=decision.status.value,
        reason=decision.reason,
        requires_human=decision.requires_human,
        checks=[c.model_dump(mode="json") for c in decision.checks],
        failed_checks=[code.value for code in decision.failed_checks],
        created_at=decision.created_at,
    )
    session.add(row)
    await session.flush()
    return row


async def list_audit_logs(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> Sequence[models.AuditLogRow]:
    stmt = (
        select(models.AuditLogRow)
        .order_by(desc(models.AuditLogRow.id))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def list_instruments(session: AsyncSession) -> Sequence[models.Instrument]:
    result = await session.execute(select(models.Instrument).order_by(models.Instrument.symbol))
    return result.scalars().all()


# --- Paper trading (orders / fills / positions) ---


async def order_exists(session: AsyncSession, idempotency_key: str) -> bool:
    stmt = select(models.OrderRow.id).where(
        models.OrderRow.idempotency_key == idempotency_key
    )
    return (await session.execute(stmt)).first() is not None


async def get_order(session: AsyncSession, order_id: str) -> models.OrderRow | None:
    return await session.get(models.OrderRow, order_id)


async def list_orders(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> Sequence[models.OrderRow]:
    stmt = (
        select(models.OrderRow)
        .order_by(desc(models.OrderRow.created_at))
        .limit(limit)
        .offset(offset)
    )
    return (await session.execute(stmt)).scalars().all()


async def list_fills(session: AsyncSession, order_id: str) -> Sequence[models.FillRow]:
    stmt = (
        select(models.FillRow)
        .where(models.FillRow.order_id == order_id)
        .order_by(models.FillRow.created_at)
    )
    return (await session.execute(stmt)).scalars().all()


async def get_position_row(
    session: AsyncSession, symbol: str, *, account: str = "paper"
) -> models.PositionRow | None:
    return await session.get(models.PositionRow, {"account": account, "symbol": symbol})


async def list_positions(
    session: AsyncSession, *, account: str = "paper"
) -> Sequence[models.PositionRow]:
    stmt = (
        select(models.PositionRow)
        .where(models.PositionRow.account == account)
        .order_by(models.PositionRow.symbol)
    )
    return (await session.execute(stmt)).scalars().all()


# --- Predictions ---


async def save_prediction(
    session: AsyncSession, prediction: MarketPrediction
) -> models.PredictionRow:
    row = models.PredictionRow(
        id=prediction.prediction_id,
        as_of=prediction.as_of,
        horizon=prediction.horizon.value,
        direction=prediction.direction.value,
        confidence=prediction.confidence,
        regime=prediction.regime.value,
        headline=prediction.headline,
        brief=prediction.brief,
        generated_by=prediction.generated_by,
        agent_count=prediction.agent_count,
        payload=prediction.model_dump(mode="json"),
        created_at=now_utc(),
    )
    session.add(row)
    await session.flush()
    return row


async def get_latest_prediction(
    session: AsyncSession,
) -> models.PredictionRow | None:
    stmt = (
        select(models.PredictionRow)
        .order_by(desc(models.PredictionRow.created_at))
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()
