"""Versioned agent output schemas (Pydantic v2).

``AgentFinding`` is the single, schema-versioned contract every agent emits.
``AwareDatetime`` fields reject naive datetimes, enforcing the point-in-time
discipline. ``Evidence.source_id`` is required and non-empty: a claim with no
source is not scorable (spec §7).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from kospi_watcher.domain.enums import (
    DataQuality,
    Horizon,
    Impact,
    MarketDirection,
    SourceType,
)

# Bump on any breaking change to AgentFinding / Evidence shape.
AGENT_FINDING_SCHEMA_VERSION = "1.0.0"


class Evidence(BaseModel):
    """A single sourced claim backing (or opposing) a finding."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(
        min_length=1,
        description="Stable source identifier. Required — claims without a "
        "source_id are excluded from scoring.",
    )
    source_type: SourceType
    title: str
    url: str | None = None
    published_at: AwareDatetime
    available_at: AwareDatetime
    claim: str


class AgentFinding(BaseModel):
    """The versioned output contract for every analysis agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = AGENT_FINDING_SCHEMA_VERSION
    agent_name: str
    agent_version: str
    as_of: AwareDatetime
    horizon: Horizon
    direction: MarketDirection
    impact: Impact
    confidence: float = Field(ge=0.0, le=1.0)
    thesis: str
    evidence: list[Evidence] = Field(default_factory=list)
    counterevidence: list[Evidence] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)
    affected_symbols: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    data_quality: DataQuality
    model_name: str
    prompt_version: str
    created_at: AwareDatetime

    @property
    def is_scorable(self) -> bool:
        """Scorable only if at least one evidence item carries a source_id."""
        return any(e.source_id for e in self.evidence)


class AgentRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AgentRun(BaseModel):
    """An execution record for one agent invocation (mock in this phase)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_name: str
    agent_version: str
    status: AgentRunStatus
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    model_name: str
    prompt_version: str
    findings: list[AgentFinding] = Field(default_factory=list)
    error: str | None = None
