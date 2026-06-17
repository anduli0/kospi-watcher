"""Prediction output contracts (Pydantic v2)."""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.enums import (
    DataQuality,
    Horizon,
    InstrumentKind,
    MarketDirection,
    MarketRegime,
    StanceLabel,
)

PREDICTION_SCHEMA_VERSION = "1.0.0"


class DeskView(BaseModel):
    """One research desk's aggregated directional view."""

    model_config = ConfigDict(extra="forbid")

    desk: str
    title: str
    lean: MarketDirection
    conviction: float = Field(ge=0.0, le=1.0)
    weight: float
    score: float  # signed directional score in [-1, 1]
    member_count: int
    responded: int
    summary: str
    top_drivers: list[str] = Field(default_factory=list)


class InstrumentStance(BaseModel):
    """House stance on one index product (long / inverse / leveraged)."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    kind: InstrumentKind
    label: StanceLabel
    rationale: str
    risk_note: str | None = None


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    probability: float = Field(ge=0.0, le=1.0)
    thesis: str
    triggers: list[str] = Field(default_factory=list)


class MarketPrediction(BaseModel):
    """The synthesized house prediction + daily brief."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = PREDICTION_SCHEMA_VERSION
    prediction_id: str
    as_of: AwareDatetime
    horizon: Horizon
    regime: MarketRegime
    direction: MarketDirection
    confidence: float = Field(ge=0.0, le=1.0)
    data_quality: DataQuality
    headline: str
    brief: str
    desk_views: list[DeskView] = Field(default_factory=list)
    instrument_stances: list[InstrumentStance] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    generated_by: str  # "mock" | "llm"
    agent_count: int
    created_at: AwareDatetime
