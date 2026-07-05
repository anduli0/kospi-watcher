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

# Internal symbols the platform understands. Includes the long/short leverage
# ladder used by predictions (1x/2x long, 1x/2x inverse).
KNOWN_SYMBOLS: tuple[str, ...] = (
    "069500",  # KODEX 200 (1x long)
    "122630",  # KODEX 레버리지 (2x long)
    "102110",  # TIGER 200 (1x long)
    "114800",  # KODEX 인버스 (1x short)
    "252670",  # KODEX 200선물인버스2X (곱버스, 2x short)
    "229200",  # KODEX KOSDAQ150
    "233740",  # KODEX 코스닥150레버리지 (2x long KOSDAQ)
    "251340",  # KODEX 코스닥150선물인버스 (1x short KOSDAQ)
    "KOSPI",
    "USDKRW",
)


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
