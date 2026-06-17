"""Standalone ASGI app for the isolated execution-gateway.

Phase 1 exposes only health/status. There is deliberately NO public submit
endpoint: the gateway's submit path is in-process only, talks to the mock
broker, and live execution is not implemented.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from kospi_watcher.config import LIVE_EXECUTION_IMPLEMENTED, get_settings
from kospi_watcher.execution_gateway.gateway import ExecutionGateway


def create_app() -> FastAPI:
    app = FastAPI(title="KOSPI-WATCHER execution-gateway", version="0.1.0")
    gateway = ExecutionGateway()

    @app.get("/health")
    async def health() -> dict[str, Any]:
        settings = get_settings()
        return {
            "status": "ok",
            "service": "execution-gateway",
            "broker_mode": gateway.broker_mode,
            "live_execution_implemented": LIVE_EXECUTION_IMPLEMENTED,
            "live_execution_armed": settings.live_execution_armed,
            "note": "isolated from agent-service; no public submit endpoint in this phase",
        }

    return app


app = create_app()
