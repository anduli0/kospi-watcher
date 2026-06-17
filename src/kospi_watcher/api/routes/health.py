"""GET /health — liveness plus DB/Redis status and trading-mode flags.

Returns NO secrets, ever (security principle §14.3/§14.4)."""

from __future__ import annotations

from fastapi import APIRouter

from kospi_watcher.api.schemas.responses import DbHealth, HealthResponse, RedisHealth
from kospi_watcher.config import get_settings
from kospi_watcher.infrastructure.db import check_database
from kospi_watcher.infrastructure.redis_client import redis_status

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    db_ok = await check_database()
    rstatus = await redis_status()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        database=DbHealth(
            connected=db_ok, backend="sqlite" if settings.is_sqlite else "postgres"
        ),
        redis=RedisHealth(
            backend=rstatus.backend, connected=rstatus.connected, detail=rstatus.detail
        ),
        trading_mode=settings.trading_mode.value,
        live_trading_enabled=settings.live_trading_enabled,
        auto_execution_enabled=settings.auto_execution_enabled,
    )
