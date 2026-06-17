"""Seed the instruments table from config/instruments.yml (idempotent upsert)."""

from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.db import models
from kospi_watcher.domain.time import now_utc

_REL = ("config", "instruments.yml")


def _instruments_path() -> Path:
    for base in (Path.cwd(), Path(__file__).resolve().parents[3]):
        candidate = base.joinpath(*_REL)
        if candidate.exists():
            return candidate
    return Path.cwd().joinpath(*_REL)


async def seed_instruments(session: AsyncSession) -> int:
    """Insert any instruments from the YAML that are not already present."""
    path = _instruments_path()
    if not path.exists():
        return 0
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    existing = {
        row for row in (await session.execute(select(models.Instrument.symbol))).scalars().all()
    }
    added = 0
    for item in data.get("instruments", []):
        if item["symbol"] in existing:
            continue
        session.add(
            models.Instrument(
                symbol=item["symbol"],
                name=item["name"],
                instrument_type=item["instrument_type"],
                market=item["market"],
                tradable=bool(item.get("tradable", False)),
                created_at=now_utc(),
            )
        )
        added += 1
    await session.flush()
    return added
