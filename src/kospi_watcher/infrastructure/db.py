"""Async SQLAlchemy engine, session factory, and declarative ``Base``.

The same ORM and migrations run on SQLite (aiosqlite, local/CI) and Postgres
(asyncpg, prod); the backend is chosen solely by ``DATABASE_URL``. Models avoid
dialect-specific column types (no JSONB / native UUID) so a single Alembic
migration covers both (see ADR-012).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from kospi_watcher.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazily create the process-wide async engine from settings."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, future=True, echo=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session and always close it."""
    async with get_sessionmaker()() as session:
        yield session


async def check_database() -> bool:
    """Lightweight health probe: ``SELECT 1``. Returns False on any failure."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def reset_engine() -> None:
    """Dispose and clear the cached engine/sessionmaker (used by tests)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
