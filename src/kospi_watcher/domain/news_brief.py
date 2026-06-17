"""News daily-brief contracts.

The daily brief is a *news roundup* — a themed digest of the day's scraped
headlines, with a one-line "market read" tying it to the agents' house view. It
is distinct from the prediction report (``MarketPrediction``): the brief
summarizes the news, the report states the forecast.
"""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

NEWS_BRIEF_SCHEMA_VERSION = "1.0.0"


class NewsHeadline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    source: str
    url: str
    published_at: AwareDatetime


class NewsTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    count: int
    headlines: list[NewsHeadline] = Field(default_factory=list)


class NewsBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = NEWS_BRIEF_SCHEMA_VERSION
    date: str  # KST calendar day, YYYY-MM-DD
    item_count: int
    summary: str  # the news-roundup narrative (one coherent digest)
    market_read: str  # one line linking the news to the agents' house view
    themes: list[NewsTheme] = Field(default_factory=list)
    generated_by: str  # "rule" (deterministic) | "llm"
    created_at: AwareDatetime
