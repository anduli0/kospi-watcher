"""Unit tests for the market-flow analysis builder (ADR-022).

Offline mode only — no network. Verifies the sector board shape/ordering, the
representative investor flows (labelled, ~zero-sum, deterministic per day), and
the narrative.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from kospi_watcher.infrastructure.marketdata.analysis import MarketAnalysisService


@pytest.fixture
def service() -> MarketAnalysisService:
    return MarketAnalysisService(offline=True)


async def test_offline_board_shape_and_sources(service: MarketAnalysisService) -> None:
    a = await service.build()
    assert a.index_symbol == "KOSPI"
    assert a.sector_source == "mock"
    assert a.flow_source == "representative"
    assert len(a.sectors) == 8
    # Every offline sector is labelled mock and carries a price.
    assert all(s.source == "mock" for s in a.sectors)
    assert all(s.price is not None for s in a.sectors)


async def test_sectors_sorted_desc_and_leaders_laggards(
    service: MarketAnalysisService,
) -> None:
    a = await service.build()
    changes = [s.change_pct for s in a.sectors]
    assert changes == sorted(changes, reverse=True)
    # leaders are positive movers, laggards negative.
    assert all(s.change_pct > 0 for s in a.leaders)
    assert all(s.change_pct < 0 for s in a.laggards)
    assert len(a.leaders) <= 3 and len(a.laggards) <= 3


async def test_flows_labelled_zero_sum_and_trend(
    service: MarketAnalysisService,
) -> None:
    a = await service.build()
    assert [f.investor for f in a.flows] == ["FOREIGN", "INSTITUTION", "INDIVIDUAL"]
    assert all(f.source == "representative" for f in a.flows)
    assert all(len(f.trend) == 5 for f in a.flows)
    # The three groups are the counterparties of one another: net ~0 (small noise).
    total_today = sum((f.net_today for f in a.flows), Decimal("0"))
    assert abs(total_today) <= Decimal("400")


async def test_deterministic_within_day(service: MarketAnalysisService) -> None:
    a = await service.build()
    fresh = await MarketAnalysisService(offline=True)._build_fresh()
    # Same KST date → identical representative flows and sector moves.
    assert [f.net_today for f in a.flows] == [f.net_today for f in fresh.flows]
    assert [s.change_pct for s in a.sectors] == [s.change_pct for s in fresh.sectors]


async def test_narrative_mentions_index_and_flows(
    service: MarketAnalysisService,
) -> None:
    a = await service.build()
    assert "코스피" in a.narrative
    assert "외국인" in a.narrative and "기관" in a.narrative and "개인" in a.narrative
