"""Historical daily closes from Yahoo (keyless) for backtesting (ADR-025).

A thin, never-raises fetch of the daily close series for an index/ETF, used by
the accuracy backtest. On any failure it returns an empty list so the caller can
fall back to a labelled offline series.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from kospi_watcher.config import get_settings
from kospi_watcher.domain.money import to_decimal
from kospi_watcher.domain.time import KST

_YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"

# Internal symbol → Yahoo symbol for the backtest universe.
_HIST_SYMBOL: dict[str, str] = {
    "KOSPI": "^KS11",
    "069500": "069500.KS",
    "229200": "229200.KS",
}


async def fetch_daily_closes(
    symbol: str = "KOSPI",
    *,
    rng: str = "5y",
    client: httpx.AsyncClient | None = None,
) -> list[Decimal]:
    """Return the chronological daily close series (oldest→newest). Never raises."""
    ysym = _HIST_SYMBOL.get(symbol, symbol)
    ua = get_settings().market_data_user_agent
    own = client is None
    client = client or httpx.AsyncClient(timeout=15.0)
    try:
        resp = await client.get(
            _YAHOO_BASE + ysym,
            params={"interval": "1d", "range": rng},
            headers={"User-Agent": ua},
        )
        if resp.status_code != 200:
            return []
        return _parse(resp.json())
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
        return []
    finally:
        if own:
            await client.aclose()


def _parse(payload: dict[str, Any]) -> list[Decimal]:
    result = payload.get("chart", {}).get("result")
    if not result:
        return []
    quote = result[0].get("indicators", {}).get("quote", [{}])[0]
    closes = quote.get("close") or []
    return [to_decimal(str(c)) for c in closes if c is not None]


async def fetch_daily_dated(
    symbol: str = "KOSPI",
    *,
    rng: str = "2y",
    client: httpx.AsyncClient | None = None,
) -> list[tuple[str, Decimal]]:
    """Return chronological (KST date, close) pairs (oldest→newest). Never raises."""
    ysym = _HIST_SYMBOL.get(symbol, symbol)
    ua = get_settings().market_data_user_agent
    own = client is None
    client = client or httpx.AsyncClient(timeout=15.0)
    try:
        resp = await client.get(
            _YAHOO_BASE + ysym,
            params={"interval": "1d", "range": rng},
            headers={"User-Agent": ua},
        )
        if resp.status_code != 200:
            return []
        return _parse_dated(resp.json())
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
        return []
    finally:
        if own:
            await client.aclose()


def _parse_dated(payload: dict[str, Any]) -> list[tuple[str, Decimal]]:
    result = payload.get("chart", {}).get("result")
    if not result:
        return []
    res = result[0]
    timestamps = res.get("timestamp") or []
    closes = res.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    out: list[tuple[str, Decimal]] = []
    for ts, c in zip(timestamps, closes, strict=False):
        if c is None or ts is None:
            continue
        date_str = datetime.fromtimestamp(ts, tz=KST).date().isoformat()
        out.append((date_str, to_decimal(str(c))))
    return out
