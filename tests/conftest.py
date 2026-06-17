"""Shared pytest fixtures.

A throwaway SQLite ``DATABASE_URL`` and the mandated RESEARCH safety defaults are
forced at *import* time — before any ``get_settings()`` call — so the test engine
can never bind to the real ``./kospi_watcher.db`` or inherit a developer's live
toggles. ``session`` / ``client`` provide a fresh-schema database per test.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

# Bind to a disposable SQLite file and pin the safety defaults. Done at module
# import (pytest loads conftest before any test module) so settings read later
# observe these values.
_TEST_DB = Path(tempfile.gettempdir()) / "kospi_watcher_pytest.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["REDIS_URL"] = ""
# Offline, deterministic market data in tests (no network calls to Yahoo).
os.environ["MARKET_DATA_PROVIDER"] = "mock"
for _k in ("LIVE_TRADING_ENABLED", "AUTO_EXECUTION_ENABLED", "TRADING_MODE"):
    os.environ.pop(_k, None)


@pytest.fixture
async def _db() -> AsyncIterator[None]:
    """Recreate the schema on a fresh engine bound to the test database."""
    from kospi_watcher.db import models  # noqa: F401 - registers tables on Base
    from kospi_watcher.infrastructure.db import Base, get_engine, reset_engine

    await reset_engine()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await reset_engine()


@pytest.fixture
async def session(_db: None) -> AsyncIterator[AsyncSession]:
    from kospi_watcher.infrastructure.db import get_sessionmaker

    async with get_sessionmaker()() as s:
        yield s


@pytest.fixture
async def client(_db: None) -> AsyncIterator[AsyncClient]:
    from httpx import ASGITransport, AsyncClient

    from kospi_watcher.api.app import create_app
    from kospi_watcher.infrastructure.marketdata import reset_market_data_provider
    from kospi_watcher.infrastructure.redis_client import reset_redis

    await reset_redis()
    await reset_market_data_provider()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
