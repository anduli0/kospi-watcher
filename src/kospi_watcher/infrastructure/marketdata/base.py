"""Market-data contracts shared by every provider.

A ``Quote`` is the single shape the rest of the system consumes. Prices are
``Decimal`` (never ``float``, ADR-008) and timestamps are timezone-aware
(ADR-009). Providers are keyed by an *internal* symbol (e.g. ``"069500"``,
``"KOSPI"``, ``"USDKRW"``); each provider maps that to its own vendor symbol.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict

from kospi_watcher.domain.money import DecimalNoFloat

# Internal symbols the platform understands in Phase 1.
KNOWN_SYMBOLS: tuple[str, ...] = ("069500", "102110", "229200", "KOSPI", "USDKRW")


class Quote(BaseModel):
    """A point-in-time price for one instrument."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    price: DecimalNoFloat
    currency: str
    as_of: AwareDatetime
    source: str  # "yahoo" | "mock"
    stale: bool = False


@runtime_checkable
class MarketDataProvider(Protocol):
    """Read-only market-data source. Implementations must never raise from
    ``get_quote``/``get_quotes`` — they return ``None`` / omit on failure so the
    risk and trading paths can degrade safely."""

    name: str

    async def get_quote(self, symbol: str) -> Quote | None: ...

    async def get_quotes(self, symbols: Sequence[str]) -> dict[str, Quote]: ...
