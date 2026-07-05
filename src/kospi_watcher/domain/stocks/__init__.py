"""Individual KOSPI/KOSDAQ stock recommendations (ADR-026).

A deterministic recommender that ranks a **broad** universe — the top ~300
KOSPI/KOSDAQ names by market cap — into short / mid / long-term top picks,
combining real per-stock price momentum with the site's house view, sector
board, BOK policy, and news. Picks are selected across the market, not a
hand-picked shortlist.
"""

from __future__ import annotations

from kospi_watcher.domain.stocks.recommender import (
    HouseContext,
    StockSignal,
    recommend,
)
from kospi_watcher.domain.stocks.schemas import (
    HorizonRecommendation,
    StockHorizon,
    StockPick,
    StockRecommendationReport,
)
from kospi_watcher.domain.stocks.universe import STOCK_UNIVERSE, StockMeta

__all__ = [
    "STOCK_UNIVERSE",
    "HorizonRecommendation",
    "HouseContext",
    "StockHorizon",
    "StockMeta",
    "StockPick",
    "StockRecommendationReport",
    "StockSignal",
    "recommend",
]
