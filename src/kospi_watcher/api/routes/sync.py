"""Site-triggered refresh — POST /api/v1/sync/run, GET /api/v1/sync/status.

Lets the (public) web ask the server to refresh news + prediction + brief on
demand and watch the progress. The heavy lifting and the abuse guards
(single-flight + cooldown) live in :mod:`kospi_watcher.briefing.sync`; this
route only reports state honestly, including which agent runtime would run
(``claude_cli`` = the owner's Claude subscription via the local CLI).
"""

from __future__ import annotations

from datetime import UTC, timedelta

from fastapi import APIRouter

from kospi_watcher.agent_service.service import AgentService
from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.responses import SyncRunResponse, SyncStatusResponse
from kospi_watcher.briefing.sync import get_sync_manager
from kospi_watcher.config import get_settings
from kospi_watcher.db import repositories
from kospi_watcher.domain.time import now_utc

router = APIRouter(tags=["sync"])


async def _status(session: SessionDep) -> SyncStatusResponse:
    settings = get_settings()
    state = get_sync_manager().status()
    latest = await repositories.get_latest_prediction(session)
    last_at = latest.created_at if latest else None
    if last_at is not None and last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=UTC)  # SQLite round-trip drops tzinfo
    stale_after = settings.sync_stale_hours
    stale = (
        last_at is None
        or now_utc() - last_at > timedelta(hours=stale_after)
    )
    service = AgentService()
    return SyncStatusResponse(
        **state,
        model=service.model_name,
        last_prediction_at=last_at,
        stale=stale,
        stale_after_hours=stale_after,
    )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status(session: SessionDep) -> SyncStatusResponse:
    return await _status(session)


@router.post("/sync/run", response_model=SyncRunResponse)
async def sync_run(session: SessionDep) -> SyncRunResponse:
    started, reason = get_sync_manager().start()
    return SyncRunResponse(started=started, reason=reason, status=await _status(session))
