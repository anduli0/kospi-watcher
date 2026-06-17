"""Process-wide market-data provider selection.

``MARKET_DATA_PROVIDER`` chooses the backend: ``yahoo`` (real, keyless) by
default, or ``mock`` (deterministic, offline). The provider is a cached
singleton; ``reset_market_data_provider`` disposes it (used by tests).
"""

from __future__ import annotations

from kospi_watcher.config import get_settings
from kospi_watcher.infrastructure.marketdata.base import MarketDataProvider
from kospi_watcher.infrastructure.marketdata.mock import MockMarketDataProvider
from kospi_watcher.infrastructure.marketdata.yahoo import YahooMarketDataProvider

_provider: MarketDataProvider | None = None


def get_market_data_provider() -> MarketDataProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.market_data_provider == "yahoo":
            _provider = YahooMarketDataProvider(
                ttl_seconds=settings.market_data_ttl_seconds,
                user_agent=settings.market_data_user_agent,
            )
        else:
            _provider = MockMarketDataProvider()
    return _provider


async def reset_market_data_provider() -> None:
    global _provider
    if isinstance(_provider, YahooMarketDataProvider):
        await _provider.aclose()
    _provider = None
