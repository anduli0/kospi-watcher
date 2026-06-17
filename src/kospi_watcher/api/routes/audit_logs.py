"""GET /api/v1/audit-logs — paginated, append-only audit log (no sensitive data)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.responses import AuditLogEntry, AuditLogPage
from kospi_watcher.db.repositories import list_audit_logs

router = APIRouter(tags=["audit-logs"])


@router.get("/audit-logs", response_model=AuditLogPage)
async def get_audit_logs(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AuditLogPage:
    rows = await list_audit_logs(session, limit=limit, offset=offset)
    return AuditLogPage(
        count=len(rows),
        limit=limit,
        offset=offset,
        items=[
            AuditLogEntry(
                id=row.id,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                summary=row.summary,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )
