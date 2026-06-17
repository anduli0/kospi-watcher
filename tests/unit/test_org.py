"""The agent organization chart: coverage, tiers, leads, weights."""

from __future__ import annotations

from kospi_watcher.domain.agents.catalog import AGENT_CATALOG
from kospi_watcher.domain.agents.org import (
    AGENT_ORG,
    DIRECTIONAL_DESKS,
    Desk,
    Tier,
    desk_of,
    desk_spec,
    is_lead,
)


def test_org_covers_every_catalog_agent_once() -> None:
    seen: list[str] = []
    for desk in AGENT_ORG:
        seen.extend(desk.members)
    assert sorted(seen) == sorted(s.name for s in AGENT_CATALOG)
    assert len(seen) == 21
    assert len(set(seen)) == 21  # no agent in two desks


def test_six_desks_with_expected_sizes() -> None:
    sizes = {d.key: len(d.members) for d in AGENT_ORG}
    assert sizes == {
        Desk.DATA_INTEGRITY: 3,
        Desk.MACRO: 6,
        Desk.FLOW_TECH: 4,
        Desk.FUNDAMENTAL: 5,
        Desk.RISK: 2,
        Desk.CHIEF: 1,
    }


def test_tiers_order_validate_analyze_synthesize() -> None:
    assert desk_spec(Desk.DATA_INTEGRITY).tier is Tier.VALIDATE
    assert all(d.tier is Tier.ANALYZE for d in DIRECTIONAL_DESKS)
    assert desk_spec(Desk.CHIEF).tier is Tier.SYNTHESIZE
    assert len(DIRECTIONAL_DESKS) == 4  # MACRO, FLOW_TECH, FUNDAMENTAL, RISK


def test_directional_weights_sum_to_one() -> None:
    total = sum(d.weight for d in AGENT_ORG)
    assert abs(total - 1.0) < 1e-9
    assert desk_spec(Desk.CHIEF).weight == 0.0


def test_lead_and_desk_lookup() -> None:
    assert desk_of("FX Agent") is Desk.MACRO
    assert desk_of("Volatility and Regime Agent") is Desk.FLOW_TECH
    assert desk_of("Chief Market Synthesizer") is Desk.CHIEF
    assert desk_of("No Such Agent") is None
    assert is_lead("Korea Macro Agent")
    assert is_lead("Chief Market Synthesizer")
    assert not is_lead("FX Agent")
