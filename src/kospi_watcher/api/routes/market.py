"""GET /api/v1/market/quotes — live (or mock) quotes for known instruments.

Read-only. Prices come from the configured market-data provider (Yahoo by
default); failures degrade to stale/missing rather than erroring.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from kospi_watcher.api.schemas.responses import MarketQuote, MarketQuotesResponse
from kospi_watcher.infrastructure.marketdata import (
    KNOWN_SYMBOLS,
    get_market_data_provider,
)

router = APIRouter(tags=["market"])


@router.get("/market/quotes", response_model=MarketQuotesResponse)
async def market_quotes(
    symbols: str = Query(
        default=",".join(KNOWN_SYMBOLS),
        description="Comma-separated internal symbols (e.g. 069500,KOSPI,USDKRW).",
    ),
) -> MarketQuotesResponse:
    requested = [s.strip() for s in symbols.split(",") if s.strip()]
    provider = get_market_data_provider()
    quotes = await provider.get_quotes(requested)
    return MarketQuotesResponse(
        provider=provider.name,
        count=len(quotes),
        quotes=[
            MarketQuote(
                symbol=q.symbol,
                price=q.price,
                currency=q.currency,
                as_of=q.as_of,
                source=q.source,
                stale=q.stale,
            )
            for q in quotes.values()
        ],
    )
