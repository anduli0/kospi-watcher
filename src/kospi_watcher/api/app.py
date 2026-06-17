"""FastAPI application factory for the main `api` service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kospi_watcher.api.routes import (
    agents,
    audit_logs,
    health,
    market,
    order_proposals,
    prediction,
    risk,
    system,
    trading,
)
from kospi_watcher.config import get_settings
from kospi_watcher.db import models  # noqa: F401  (register tables on Base.metadata)
from kospi_watcher.db.seed import seed_instruments
from kospi_watcher.infrastructure.db import Base, get_engine, get_sessionmaker
from kospi_watcher.logging_config import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(json_logs=settings.log_json, level=settings.log_level)
    # Dev convenience: ensure the schema exists and seed instruments. In prod the
    # schema is created by Alembic, so create_all is a harmless no-op there.
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with get_sessionmaker()() as session:
        await seed_instruments(session)
        await session.commit()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="KOSPI-WATCHER API — analysis & risk only. No live trading.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    app.include_router(health.router)
    for router in (
        system.router,
        agents.router,
        prediction.router,
        market.router,
        order_proposals.router,
        risk.router,
        trading.router,
        audit_logs.router,
    ):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
