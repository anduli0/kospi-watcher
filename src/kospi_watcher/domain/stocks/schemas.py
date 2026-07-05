"""Output contracts for the stock-recommendation surface (ADR-026)."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.enums import MarketDirection, MarketRegime
from kospi_watcher.domain.money import DecimalNoFloat


class StockHorizon(StrEnum):
    SHORT = "SHORT"  # 단기 (1~4주)
    MID = "MID"  # 중기 (1~3개월)
    LONG = "LONG"  # 장기 (6~12개월)


class StockPick(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    code: str
    name: str
    sector: str
    themes: list[str]
    price: DecimalNoFloat | None
    momentum_pct: Decimal | None  # the horizon's lookback return, %
    stretch_pct: Decimal | None  # price vs 120-day SMA, % (과열/이격)
    overheated: bool  # very extended above the long-term trend (bubble/reversion risk)
    conviction: str  # "적극매수" | "매수" | "관심"
    score: float
    drivers: list[str]  # short bullet reasons (Korean)
    rationale: str  # one-line thesis
    detail: str  # fuller horizon-specific explanation (shown on click)
    news_catalyst: str | None  # headline if the name was in recent news


class HorizonRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon: StockHorizon
    label: str  # "단기 (1~4주)"
    approach: str  # what drives this horizon (Korean)
    picks: list[StockPick]


class StockRecommendationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: AwareDatetime
    house_direction: MarketDirection
    house_regime: MarketRegime
    monetary_stance: str  # "HAWKISH" | "NEUTRAL" | "DOVISH"
    universe_size: int
    price_source: str  # "yahoo" | "mock"
    horizons: list[HorizonRecommendation] = Field(default_factory=list)
    disclaimer: str
