"""Persistence layer: repositories, Decimal-as-TEXT precision, Redis fallback."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.db import models
from kospi_watcher.db.repositories import (
    add_audit_log,
    list_audit_logs,
    save_agent_run,
    save_proposal,
    save_risk_decision,
)
from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.registry import AgentRegistry
from kospi_watcher.domain.enums import (
    AuditAction,
    InstrumentType,
    OrderSide,
    OrderType,
)
from kospi_watcher.domain.risk.engine import RiskContext, RiskEngine
from kospi_watcher.domain.risk.limits import load_risk_limits
from kospi_watcher.domain.risk.schemas import OrderProposal
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.redis_client import get_redis_client, redis_status, reset_redis


def _proposal(idempotency_key: str = "idem-1") -> OrderProposal:
    return OrderProposal(
        proposal_id=f"p-{idempotency_key}",
        created_at=now_utc(),
        symbol="069500",
        instrument_type=InstrumentType.ETF,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=Decimal("35000.25"),
        strategy_id="baseline-momentum-v0",
        strategy_version="0.1.0",
        idempotency_key=idempotency_key,
    )


async def test_proposal_roundtrip_preserves_decimal(session: AsyncSession) -> None:
    await save_proposal(session, _proposal())
    await session.commit()
    row = (
        await session.execute(select(models.OrderProposalRow))
    ).scalar_one()
    # Stored as TEXT, so the exact Decimal survives (no float rounding).
    assert row.limit_price == Decimal("35000.25")
    assert isinstance(row.limit_price, Decimal)


async def test_duplicate_idempotency_key_violates_unique(session: AsyncSession) -> None:
    await save_proposal(session, _proposal("dup"))
    await session.commit()
    # save_proposal flushes internally, so the unique violation surfaces here.
    with pytest.raises(IntegrityError):
        await save_proposal(session, _proposal("dup"))
    await session.rollback()


async def test_agent_run_persists_findings(session: AsyncSession) -> None:
    run = AgentRegistry().run("FX Agent", AgentContext(as_of=now_utc(), universe=("069500",)))
    await save_agent_run(session, run)
    await session.commit()
    findings = (
        await session.execute(
            select(func.count()).select_from(models.AgentFindingRow)
        )
    ).scalar_one()
    assert findings == len(run.findings) >= 1


async def test_risk_decision_persists(session: AsyncSession) -> None:
    proposal = _proposal("risk")
    ctx = RiskContext(as_of=now_utc(), market_open=True, last_price=Decimal("35000"))
    decision = RiskEngine(load_risk_limits()).evaluate(proposal, ctx)
    await save_risk_decision(session, decision)
    await session.commit()
    row = (await session.execute(select(models.RiskDecisionRow))).scalar_one()
    assert row.status == decision.status.value
    assert isinstance(row.checks, list) and row.checks


async def test_audit_log_is_append_and_listable(session: AsyncSession) -> None:
    await add_audit_log(
        session,
        action=AuditAction.RISK_EVALUATED,
        entity_type="risk_decision",
        entity_id="d-1",
        summary="test entry",
    )
    await session.commit()
    rows = await list_audit_logs(session, limit=10)
    assert len(rows) == 1
    assert rows[0].action == AuditAction.RISK_EVALUATED.value


async def test_redis_falls_back_to_fakeredis() -> None:
    # With REDIS_URL unset (see conftest) we get the in-memory fakeredis backend.
    await reset_redis()
    redis = await get_redis_client()
    await redis.set("k", "v")
    assert await redis.get("k") == "v"
    status = await redis_status()
    assert status.backend == "fakeredis"
    assert status.connected is True
