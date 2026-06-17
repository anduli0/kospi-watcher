"""Create all tables if missing (idempotent). Used by the local launcher.

Uses ``create_all`` (not Alembic) because the API lifespan also creates the
schema this way for local/SQLite mode; running ``alembic upgrade head`` over a
create_all-built DB conflicts (tables already exist, no alembic_version).
"""

from __future__ import annotations

import asyncio

from kospi_watcher.db import models  # noqa: F401 - registers tables on Base
from kospi_watcher.infrastructure.db import Base, get_engine, reset_engine


async def _main() -> None:
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await reset_engine()


if __name__ == "__main__":
    asyncio.run(_main())
