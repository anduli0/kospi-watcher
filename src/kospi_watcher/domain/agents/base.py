"""Agent protocol, run context, and deterministic mock agent.

The :class:`MockAgent` performs **no** real Anthropic call and has **no** access
to order execution. Output is deterministic in ``(name, as_of)`` so tests are
reproducible, and every field is flagged as MOCK so it can never be mistaken for
real market data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from kospi_watcher.domain.agents.catalog import AgentSpec
from kospi_watcher.domain.agents.schemas import AgentFinding, Evidence
from kospi_watcher.domain.enums import DataQuality, SourceType
from kospi_watcher.domain.time import ensure_aware

MOCK_MODEL_NAME = "mock-deterministic-v0"
MOCK_PROMPT_VERSION = "mock-2026.06"

_CATEGORY_SOURCE: dict[str, SourceType] = {
    "DATA_INTEGRITY": SourceType.PRICE_DATA,
    "NEWS": SourceType.NEWS,
    "DISCLOSURE": SourceType.DISCLOSURE,
    "MACRO": SourceType.MACRO_RELEASE,
    "GEOPOLITICS": SourceType.NEWS,
    "FLOW": SourceType.FLOW_DATA,
    "TECHNICAL": SourceType.PRICE_DATA,
    "REGIME": SourceType.PRICE_DATA,
    "FUNDAMENTAL": SourceType.RESEARCH_NOTE,
    "SECTOR": SourceType.RESEARCH_NOTE,
    "STRUCTURAL": SourceType.RESEARCH_NOTE,
    "RISK": SourceType.OTHER,
    "SYNTHESIS": SourceType.OTHER,
}


@dataclass(frozen=True)
class AgentContext:
    """Inputs shared by every agent in a run."""

    as_of: datetime
    universe: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        ensure_aware(self.as_of)


@runtime_checkable
class AnalysisAgent(Protocol):
    """Structural type every agent satisfies. Note: no order-execution surface."""

    name: str
    version: str
    category: str

    def run(self, ctx: AgentContext) -> list[AgentFinding]: ...


class MockAgent:
    """Deterministic, schema-valid mock implementation of an analysis agent."""

    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec
        self.name = spec.name
        self.version = spec.version
        self.category = spec.category

    def _seed(self, as_of: datetime) -> int:
        digest = hashlib.sha256(f"{self.name}|{as_of.isoformat()}".encode()).hexdigest()
        return int(digest[:8], 16)

    def run(self, ctx: AgentContext) -> list[AgentFinding]:
        seed = self._seed(ctx.as_of)
        confidence = round(0.40 + (seed % 50) / 100.0, 2)
        published = ctx.as_of - timedelta(hours=1 + seed % 5)
        available = published + timedelta(minutes=5)
        source_type = _CATEGORY_SOURCE.get(self.category, SourceType.OTHER)

        evidence = Evidence(
            source_id=f"MOCK-{seed:08x}",
            source_type=source_type,
            title="MOCK DATA — NOT REAL MARKET DATA",
            url=None,
            published_at=published,
            available_at=available,
            claim=f"[MOCK] {self.name} synthetic evidence (seed={seed:08x}).",
        )
        finding = AgentFinding(
            agent_name=self.name,
            agent_version=self.version,
            as_of=ctx.as_of,
            horizon=self.spec.horizon,
            direction=self.spec.direction,
            impact=self.spec.impact,
            confidence=confidence,
            thesis=f"[MOCK] {self.spec.summary}",
            evidence=[evidence],
            counterevidence=[],
            affected_sectors=list(self.spec.sectors),
            affected_symbols=list(ctx.universe[:3]),
            invalidation_conditions=[
                f"[MOCK] 시장 국면이 반전되면 {self.name}의 논거는 무효화된다."
            ],
            data_quality=DataQuality.OK,
            model_name=MOCK_MODEL_NAME,
            prompt_version=MOCK_PROMPT_VERSION,
            created_at=ctx.as_of,
        )
        return [finding]
