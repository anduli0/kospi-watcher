"""Standalone ASGI app for the isolated agent-service.

Runs analysis only; it has no order-execution surface. Kept separate from the
main API to demonstrate service-level isolation from the Execution Gateway.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from kospi_watcher.agent_service.service import AgentService
from kospi_watcher.api.schemas.requests import MockRunRequest
from kospi_watcher.api.schemas.responses import AgentInfo, AgentListResponse
from kospi_watcher.domain.agents.registry import AgentNotFoundError
from kospi_watcher.domain.agents.schemas import AgentRun


def create_app() -> FastAPI:
    app = FastAPI(title="KOSPI-WATCHER agent-service", version="0.1.0")
    service = AgentService()

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "agent-service",
            "agent_count": len(service.names()),
            "note": "analysis only; no order authority",
        }

    @app.get("/agents", response_model=AgentListResponse)
    async def agents() -> AgentListResponse:
        specs = service.list_specs()
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

    @app.post("/run", response_model=AgentRun)
    async def run(req: MockRunRequest) -> AgentRun:
        try:
            return service.run_mock(req.agent_name, tuple(req.universe))
        except AgentNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=f"unknown agent: {req.agent_name}"
            ) from exc

    return app


app = create_app()
