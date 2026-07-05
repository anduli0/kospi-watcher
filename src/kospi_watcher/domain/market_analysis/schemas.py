"""Schemas for the market-flow analysis surface (ADR-022).

These describe *what moved the index today*: the per-sector board (which
industries led / lagged) and the net buy/sell flow of the three Korean investor
groups (외국인 / 기관 / 개인). Pure data — no I/O, no ``float`` (ADR-008).

Sector moves are sourced live from Yahoo (``source="yahoo"``) and fall back to a
clearly-labelled offline value (``source="mock"``). Investor flows have no keyless
real-time feed, so they are **representative** (``source="representative"``),
deterministically derived from the index move and the date — labelled as such in
the schema and the UI, never presented as a real KRX print.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict

from kospi_watcher.domain.money import DecimalNoFloat


class SectorMove(BaseModel):
    """One industry sector's move on the day (signed % change)."""

    model_config = ConfigDict(extra="forbid")

    key: str  # stable english key, e.g. "semiconductor"
    name: str  # Korean display name, e.g. "반도체"
    symbol: str  # representative sector ETF code, e.g. "091160"
    price: DecimalNoFloat | None
    change_pct: Decimal  # signed percent, e.g. Decimal("-1.23")
    source: str  # "yahoo" | "mock"


class InvestorTrendPoint(BaseModel):
    """Net buy (억원, signed) for one investor group on one KST day."""

    model_config = ConfigDict(extra="forbid")

    date: str  # KST YYYY-MM-DD
    net: Decimal  # 억원, + = net buy, - = net sell


class InvestorFlow(BaseModel):
    """A Korean investor group's net flow today plus a short daily trend."""

    model_config = ConfigDict(extra="forbid")

    investor: str  # "FOREIGN" | "INSTITUTION" | "INDIVIDUAL"
    label: str  # "외국인" | "기관" | "개인"
    net_today: Decimal  # 억원, signed
    net_5d: Decimal  # 억원, signed cumulative over the trend window
    trend: list[InvestorTrendPoint]
    source: str  # "representative" | "mock" — never a real KRX print


class MarketAnalysis(BaseModel):
    """The assembled 'what moved KOSPI today' board."""

    model_config = ConfigDict(extra="forbid")

    as_of: AwareDatetime
    index_symbol: str  # "KOSPI"
    index_price: DecimalNoFloat | None
    index_change_pct: Decimal | None
    sectors: list[SectorMove]  # all sectors, sorted by change desc
    leaders: list[SectorMove]  # top movers up
    laggards: list[SectorMove]  # top movers down
    flows: list[InvestorFlow]  # 외국인 / 기관 / 개인
    narrative: str  # one-line Korean read tying sectors + flows together
    sector_source: str  # dominant sector source ("yahoo" | "mock")
    flow_source: str  # "representative" | "mock"
