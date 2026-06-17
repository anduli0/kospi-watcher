"""The analysis-agent organization chart.

The 21 agents are arranged as a research firm: five **desks** (each with a
designated *lead*) feed a **Chief** synthesizer. Work runs in **tiers** —
data/integrity validates first, the analysis desks run in parallel, then the
Chief synthesizes. Each desk carries a directional ``weight`` the Chief uses
when combining desk views into the house prediction.

This module is pure metadata over ``catalog.py`` — it does not run anything; the
orchestration lives in ``prediction/synthesizer.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from kospi_watcher.domain.agents.catalog import AGENT_CATALOG


class Desk(StrEnum):
    DATA_INTEGRITY = "DATA_INTEGRITY"
    MACRO = "MACRO"
    FLOW_TECH = "FLOW_TECH"
    FUNDAMENTAL = "FUNDAMENTAL"
    RISK = "RISK"
    CHIEF = "CHIEF"


class Tier(StrEnum):
    """Execution order — lower tiers run (and inform) first."""

    VALIDATE = "VALIDATE"  # tier 0: data quality gate
    ANALYZE = "ANALYZE"  # tier 1: the directional desks (parallel)
    SYNTHESIZE = "SYNTHESIZE"  # tier 2: the Chief


@dataclass(frozen=True)
class DeskSpec:
    key: Desk
    title_ko: str
    tier: Tier
    weight: float  # directional weight in the Chief's synthesis (desks sum ~1.0)
    lead: str  # agent name of the desk lead
    members: tuple[str, ...] = field(default_factory=tuple)

    def __contains__(self, agent_name: str) -> bool:
        return agent_name in self.members


# Desk roster. Member names MUST match catalog.py exactly. Directional weights
# apply only to the analysis desks; DATA_INTEGRITY gates data quality and gets a
# small directional weight, and CHIEF is the synthesizer (weight 0).
AGENT_ORG: tuple[DeskSpec, ...] = (
    DeskSpec(
        Desk.DATA_INTEGRITY,
        "데이터·검증 데스크",
        Tier.VALIDATE,
        0.10,
        lead="Market Data Integrity Agent",
        members=(
            "Market Data Integrity Agent",
            "News Deduplication Agent",
            "Source Verification Agent",
        ),
    ),
    DeskSpec(
        Desk.MACRO,
        "거시·국제 데스크",
        Tier.ANALYZE,
        0.24,
        lead="Korea Macro Agent",
        members=(
            "Korea Macro Agent",
            "Global Growth Agent",
            "Rates and Liquidity Agent",
            "FX Agent",
            "Commodity and Energy Agent",
            "Geopolitics and Trade Agent",
        ),
    ),
    DeskSpec(
        Desk.FLOW_TECH,
        "수급·기술 데스크",
        Tier.ANALYZE,
        0.26,
        lead="Foreign and Institutional Flow Agent",
        members=(
            "Foreign and Institutional Flow Agent",
            "Derivatives and Program Agent",
            "Breadth and Technical Agent",
            "Volatility and Regime Agent",
        ),
    ),
    DeskSpec(
        Desk.FUNDAMENTAL,
        "실적·섹터 데스크",
        Tier.ANALYZE,
        0.24,
        lead="Earnings and Valuation Agent",
        members=(
            "Earnings and Valuation Agent",
            "Technology and Semiconductor Agent",
            "Industrial and Export Agent",
            "Domestic Demand and Defensive Agent",
            "Structural Growth Scout",
        ),
    ),
    DeskSpec(
        Desk.RISK,
        "리스크·레드팀 데스크",
        Tier.ANALYZE,
        0.16,
        lead="Red-Team and Risk Agent",
        members=(
            "Red-Team and Risk Agent",
            "Disclosure and Corporate Event Agent",
        ),
    ),
    DeskSpec(
        Desk.CHIEF,
        "수석 신디사이저",
        Tier.SYNTHESIZE,
        0.0,
        lead="Chief Market Synthesizer",
        members=("Chief Market Synthesizer",),
    ),
)

_DESK_BY_AGENT: dict[str, Desk] = {
    name: desk.key for desk in AGENT_ORG for name in desk.members
}

ANALYSIS_DESKS: tuple[DeskSpec, ...] = tuple(
    d for d in AGENT_ORG if d.key not in (Desk.CHIEF,)
)
DIRECTIONAL_DESKS: tuple[DeskSpec, ...] = tuple(
    d for d in AGENT_ORG if d.tier is Tier.ANALYZE
)

# Every catalog agent belongs to exactly one desk, and desks add up to 21.
_catalog_names = {spec.name for spec in AGENT_CATALOG}
assert set(_DESK_BY_AGENT) == _catalog_names, "org must cover exactly the catalog"  # noqa: S101
assert sum(len(d.members) for d in AGENT_ORG) == 21, "org must contain 21 agents"  # noqa: S101


def desk_of(agent_name: str) -> Desk | None:
    return _DESK_BY_AGENT.get(agent_name)


def desk_spec(key: Desk) -> DeskSpec:
    return next(d for d in AGENT_ORG if d.key is key)


def is_lead(agent_name: str) -> bool:
    return any(d.lead == agent_name for d in AGENT_ORG)
