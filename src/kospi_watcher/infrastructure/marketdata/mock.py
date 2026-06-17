"""Deterministic offline market-data provider.

Used in tests and whenever the real provider is disabled or unreachable. Prices
are fixed, plausible, and clearly flagged ``source="mock"`` / ``stale=True`` so
they can never be mistaken for live quotes.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.marketdata.base import Quote

_MOCK_PRICES: dict[str, tuple[Decimal, str]] = {
    "069500": (Decimal("35000"), "KRW"),
    "102110": (Decimal("36500"), "KRW"),
    "229200": (Decimal("12500"), "KRW"),
    "KOSPI": (Decimal("2700.00"), "KRW"),
    "USDKRW": (Decimal("1350.00"), "KRW"),
}


class MockMarketDataProvider:
    """Returns fixed, clearly-labelled prices. Never touches the network."""

    name = "mock"

    async def get_quote(self, symbol: str) -> Quote | None:
        entry = _MOCK_PRICES.get(symbol)
        if entry is None:
            return None
        price, currency = entry
        return Quote(
            symbol=symbol,
            price=price,
            currency=currency,
            as_of=now_utc(),
            source="mock",
            stale=True,
        )

    async def get_quotes(self, symbols: Sequence[str]) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for sym in symbols:
            q = await self.get_quote(sym)
            if q is not None:
                out[sym] = q
        return out
