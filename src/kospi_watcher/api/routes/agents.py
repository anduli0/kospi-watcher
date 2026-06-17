"""GET /api/v1/agents and POST /api/v1/agents/mock-run."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from kospi_watcher.agent_service.service import AgentService
from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.requests import MockRunRequest
from kospi_watcher.api.schemas.responses import AgentInfo, AgentListResponse
from kospi_watcher.db.repositories import add_audit_log, save_agent_run
from kospi_watcher.domain.agents.registry import AgentNotFoundError
from kospi_watcher.domain.agents.schemas import AgentRun
from kospi_watcher.domain.enums import AuditAction

router = APIRouter(tags=["agents"])
_service = AgentService()


@router.get("/agents", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    specs = _service.list_specs()
    return AgentListResponse(
        count=len(specs),
        agents=[
            AgentInfo(
                name=s.name,
                version=s.version,
                category=s.category,
                summary=s.summary,
                enabled=True,
            )
            for s in specs
        ],
    )


@router.post("/agents/mock-run", response_model=AgentRun)
async def mock_run(req: MockRunRequest, session: SessionDep) -> AgentRun:
    try:
        run = _service.run_mock(req.agent_name, tuple(req.universe))
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown agent: {req.agent_name}") from exc

    await _persist_run(session, run, label="mock run")
    return run


@router.post("/agents/run", response_model=AgentRun)
async def run_agent(req: MockRunRequest, session: SessionDep) -> AgentRun:
    """Run one agent with the configured runtime (real LLM when armed, else the
    deterministic mock — LLM failures fall back to mock automatically)."""
    try:
        run = await _service.run(req.agent_name, tuple(req.universe))
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown agent: {req.agent_name}") from exc

    await _persist_run(session, run, label=f"{_service.runtime_name} run")
    return run


async def _persist_run(session: SessionDep, run: AgentRun, *, label: str) -> None:
    await save_agent_run(session, run)
    await add_audit_log(
        session,
        action=AuditAction.AGENT_RUN,
        entity_type="agent_run",
        entity_id=run.run_id,
        summary=f"{label} {run.agent_name} -> {run.status.value}",
        payload={"agent": run.agent_name, "findings": len(run.findings)},
    )
    await session.commit()
