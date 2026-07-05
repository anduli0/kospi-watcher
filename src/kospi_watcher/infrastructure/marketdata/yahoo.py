"""Real, keyless market-data provider backed by Yahoo Finance.

Pulls live quotes for the KOSPI index, USD/KRW, and the tradable KOSPI200 ETFs
via the public chart endpoint (a ``User-Agent`` header is required, otherwise
Yahoo returns HTTP 429). Results are cached for a short TTL and the provider
never raises: on any error it returns the last cached value (flagged stale) or
``None`` so the risk/trading paths degrade safely.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import httpx

from kospi_watcher.domain.money import to_decimal
from kospi_watcher.domain.time import UTC, now_utc
from kospi_watcher.infrastructure.marketdata.base import Quote

_YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Internal symbol -> Yahoo symbol.
_SYMBOL_MAP: dict[str, str] = {
    "069500": "069500.KS",
    "122630": "122630.KS",
    "102110": "102110.KS",
    "114800": "114800.KS",
    "252670": "252670.KS",
    "229200": "229200.KS",
    "233740": "233740.KS",
    "251340": "251340.KS",
    "KOSPI": "^KS11",
    "USDKRW": "KRW=X",
}


class YahooMarketDataProvider:
    """Live quotes from Yahoo Finance. Pass ``client`` to inject a transport in
    tests; otherwise an ``httpx.AsyncClient`` is created lazily."""

    name = "yahoo"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        ttl_seconds: int = 60,
        user_agent: str = _DEFAULT_UA,
        timeout: float = 8.0,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._ttl = ttl_seconds
        self._ua = user_agent
        self._timeout = timeout
        self._cache: dict[str, tuple[float, Quote]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def get_quote(self, symbol: str) -> Quote | None:
        ysym = _SYMBOL_MAP.get(symbol)
        if ysym is None:
            return None
        now = time.monotonic()
        cached = self._cache.get(symbol)
        if cached is not None and cached[0] > now:
            return cached[1]
        try:
            client = await self._get_client()
            resp = await client.get(
                _YAHOO_BASE + ysym,
                params={"interval": "1d", "range": "1d"},
                headers={"User-Agent": self._ua},
            )
            if resp.status_code != 200:
                return self._fallback(symbol)
            quote = self._parse(symbol, resp.json())
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return self._fallback(symbol)
        if quote is not None:
            self._cache[symbol] = (now + self._ttl, quote)
        return quote

    def _fallback(self, symbol: str) -> Quote | None:
        cached = self._cache.get(symbol)
        if cached is not None:
            return cached[1].model_copy(update={"stale": True})
        return None

    @staticmethod
    def _parse(symbol: str, payload: dict[str, Any]) -> Quote | None:
        result = payload.get("chart", {}).get("result")
        if not result:
            return None
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            return None
        ts = meta.get("regularMarketTime")
        as_of = datetime.fromtimestamp(ts, tz=UTC) if ts else now_utc()
        return Quote(
            symbol=symbol,
            price=to_decimal(str(price)),
            currency=meta.get("currency", "KRW"),
            as_of=as_of,
            source="yahoo",
            stale=False,
        )

    async def get_quotes(self, symbols: Sequence[str]) -> dict[str, Quote]:
        results = await asyncio.gather(*(self.get_quote(s) for s in symbols))
        return {
            sym: quote
            for sym, quote in zip(symbols, results, strict=True)
            if quote is not None
        }

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
