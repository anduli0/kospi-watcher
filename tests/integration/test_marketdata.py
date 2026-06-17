"""Market-data providers: Yahoo parsing (offline), failure fallback, mock."""

from __future__ import annotations

from decimal import Decimal

import httpx

from kospi_watcher.infrastructure.marketdata import MockMarketDataProvider
from kospi_watcher.infrastructure.marketdata.yahoo import YahooMarketDataProvider

_SAMPLE = {
    "chart": {
        "result": [
            {
                "meta": {
                    "symbol": "069500.KS",
                    "regularMarketPrice": 139285.0,
                    "currency": "KRW",
                    "regularMarketTime": 1_718_000_000,
                }
            }
        ]
    }
}


def _provider(handler: httpx.MockTransport) -> YahooMarketDataProvider:
    return YahooMarketDataProvider(client=httpx.AsyncClient(transport=handler))


async def test_yahoo_parses_quote_offline() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=_SAMPLE))
    provider = _provider(transport)
    quote = await provider.get_quote("069500")
    assert quote is not None
    assert quote.price == Decimal("139285.0")
    assert quote.currency == "KRW"
    assert quote.source == "yahoo"
    assert quote.stale is False
    assert quote.as_of.tzinfo is not None  # timezone-aware
    await provider.aclose()


async def test_yahoo_unknown_symbol_returns_none() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=_SAMPLE))
    provider = _provider(transport)
    assert await provider.get_quote("NOT_A_SYMBOL") is None
    await provider.aclose()


async def test_yahoo_http_error_degrades_to_none() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(429, text="rate limited"))
    provider = _provider(transport)
    # No cache yet, so a failed fetch yields None rather than raising.
    assert await provider.get_quote("069500") is None
    await provider.aclose()


async def test_yahoo_serves_stale_cache_on_failure() -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json=_SAMPLE)
        return httpx.Response(500, text="boom")

    provider = YahooMarketDataProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ttl_seconds=0,  # force a refetch on the second call
    )
    first = await provider.get_quote("069500")
    assert first is not None and first.stale is False
    second = await provider.get_quote("069500")
    assert second is not None and second.stale is True  # last good value, flagged
    await provider.aclose()


async def test_mock_provider_returns_fixed_prices() -> None:
    provider = MockMarketDataProvider()
    quotes = await provider.get_quotes(["069500", "USDKRW", "NOPE"])
    assert set(quotes) == {"069500", "USDKRW"}
    assert quotes["069500"].source == "mock"
    assert quotes["069500"].stale is True
