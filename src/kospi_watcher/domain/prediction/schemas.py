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
from kospi_watcher.domain.prediction.accuracy_track import Calibration
from kospi_watcher.domain.prediction.monetary_policy import MonetaryPolicySignal
from kospi_watcher.domain.prediction.trend_signal import TrendSignal

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


class AgentPosition(BaseModel):
    """One agent's stated position inside a desk discussion."""

    model_config = ConfigDict(extra="forbid")

    agent: str
    is_lead: bool
    direction: MarketDirection
    confidence: float = Field(ge=0.0, le=1.0)
    note: str


class DeskDeliberation(BaseModel):
    """How one desk debated and the lead reconciled it into a desk view."""

    model_config = ConfigDict(extra="forbid")

    desk: str
    title: str
    consensus: MarketDirection
    agreement: float = Field(ge=0.0, le=1.0)
    positions: list[AgentPosition] = Field(default_factory=list)
    dissent: list[str] = Field(default_factory=list)
    lead_note: str


class ChiefDeliberation(BaseModel):
    """How the Chief weighed the desks into the house view."""

    model_config = ConfigDict(extra="forbid")

    overall: MarketDirection
    aligned_desks: list[str] = Field(default_factory=list)
    conflicted_desks: list[str] = Field(default_factory=list)
    note: str


class Deliberation(BaseModel):
    """The full discussion that produced the prediction (desks → Chief)."""

    model_config = ConfigDict(extra="forbid")

    desks: list[DeskDeliberation] = Field(default_factory=list)
    chief: ChiefDeliberation


class MarketPrediction(BaseModel):
    """The synthesized house prediction + daily brief."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = PREDICTION_SCHEMA_VERSION
    prediction_id: str
    as_of: AwareDatetime
    subject: str = "코스피200 지수 방향"  # what this prediction is about
    horizon: Horizon
    horizon_label: str = ""  # human label for the horizon
    regime: MarketRegime
    direction: MarketDirection
    confidence: float = Field(ge=0.0, le=1.0)
    data_quality: DataQuality
    headline: str
    brief: str
    desk_views: list[DeskView] = Field(default_factory=list)
    deliberation: Deliberation | None = None
    monetary_policy: MonetaryPolicySignal | None = None
    trend_signal: TrendSignal | None = None
    calibration: Calibration | None = None
    instrument_stances: list[InstrumentStance] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    news_refs: list[str] = Field(default_factory=list)
    generated_by: str  # "mock" | "llm" | "claude_cli"
    agent_count: int
    created_at: AwareDatetime
