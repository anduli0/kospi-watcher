"""News daily-brief contracts.

The daily brief is a *news roundup* — a themed digest of the day's scraped
headlines, with a one-line "market read" tying it to the agents' house view. It
is distinct from the prediction report (``MarketPrediction``): the brief
summarizes the news, the report states the forecast.
"""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

NEWS_BRIEF_SCHEMA_VERSION = "1.3.0"


class NewsHeadline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    source: str
    url: str
    published_at: AwareDatetime


class NewsKeyPoint(BaseModel):
    """A notable headline surfaced into the brief's highlights — clickable."""

    model_config = ConfigDict(extra="forbid")

    tag: str  # theme angle, e.g. "지수 전반"
    title: str
    source: str
    url: str


class NewsTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    count: int
    read: str = ""  # one-line read of what this theme means for the market
    headlines: list[NewsHeadline] = Field(default_factory=list)


class NewsBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = NEWS_BRIEF_SCHEMA_VERSION
    date: str  # KST calendar day, YYYY-MM-DD
    item_count: int
    is_trading_day: bool = True  # False on weekends/휴장일 — prose frames next session
    summary: str  # the news-roundup narrative (a multi-paragraph digest)
    market_read: str  # the actionable investor takeaway, tied to the house view
    key_points: list[NewsKeyPoint] = Field(default_factory=list)  # notable headlines
    themes: list[NewsTheme] = Field(default_factory=list)
    generated_by: str  # "rule" (deterministic) | "llm"
    created_at: AwareDatetime
