"""GET /api/v1/system/status — versions, server time, flags, data-source placeholders."""

from __future__ import annotations

from fastapi import APIRouter

from kospi_watcher.api.schemas.responses import DataSourceStatus, SystemStatusResponse
from kospi_watcher.config import (
    LIVE_EXECUTION_IMPLEMENTED,
    PAPER_EXECUTION_IMPLEMENTED,
    get_settings,
)
from kospi_watcher.domain.agents.registry import get_registry
from kospi_watcher.domain.time import now_utc, to_kst

router = APIRouter(tags=["system"])

# Market prices (KOSPI/USDKRW/ETFs) are live via the configured provider; the
# broker/disclosure/macro feeds below remain unwired placeholders in this phase.
_PLACEHOLDER_SOURCES = ("KIS", "Kiwoom", "DART", "ECOS", "FRED", "NAVER")


@router.get("/system/status", response_model=SystemStatusResponse)
async def system_status() -> SystemStatusResponse:
    settings = get_settings()
    now = now_utc()
    return SystemStatusResponse(
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        server_time_utc=now,
        server_time_kst=to_kst(now),
        trading_mode=settings.trading_mode.value,
        feature_flags={
            "live_trading_enabled": settings.live_trading_enabled,
            "auto_execution_enabled": settings.auto_execution_enabled,
            "live_execution_implemented": LIVE_EXECUTION_IMPLEMENTED,
            "paper_execution_implemented": PAPER_EXECUTION_IMPLEMENTED,
        },
        data_sources=[
            DataSourceStatus(
                name=f"market-data:{settings.market_data_provider}", status="active"
            ),
            *[
                DataSourceStatus(name=name, status="not_configured")
                for name in _PLACEHOLDER_SOURCES
            ],
        ],
        agent_count=len(get_registry()),
        agent_runtime=(
            "llm"
            if settings.agent_runtime == "llm" and settings.anthropic_api_key.get_secret_value()
            else "mock"
        ),
    )
