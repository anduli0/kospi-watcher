"""API response models. Only declared fields are serialised — secrets can never
leak because they are not part of any response schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from kospi_watcher.domain.risk.schemas import RiskDecision


class DbHealth(BaseModel):
    connected: bool
    backend: str


class RedisHealth(BaseModel):
    backend: str
    connected: bool
    detail: str


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: DbHealth
    redis: RedisHealth
    trading_mode: str
    live_trading_enabled: bool
    auto_execution_enabled: bool


class DataSourceStatus(BaseModel):
    name: str
    status: str


class SystemStatusResponse(BaseModel):
    app: str
    version: str
    environment: str
    server_time_utc: datetime
    server_time_kst: datetime
    trading_mode: str
    feature_flags: dict[str, bool]
    data_sources: list[DataSourceStatus]
    agent_count: int
    agent_runtime: str


class MarketQuote(BaseModel):
    symbol: str
    price: Decimal
    currency: str
    as_of: datetime
    source: str
    stale: bool


class MarketQuotesResponse(BaseModel):
    provider: str
    count: int
    quotes: list[MarketQuote]


class AgentInfo(BaseModel):
    name: str
    version: str
    category: str
    summary: str
    enabled: bool


class AgentListResponse(BaseModel):
    count: int
    agents: list[AgentInfo]


class ValidationResponse(BaseModel):
    valid: bool
    proposal_id: str
    detail: str


class FillResponse(BaseModel):
    id: str
    symbol: str
    side: str
    quantity: int
    price: Decimal
    liquidity: str
    created_at: datetime


class OrderResponse(BaseModel):
    id: str
    proposal_id: str
    risk_decision_id: str | None
    symbol: str
    side: str
    order_type: str
    quantity: int
    limit_price: Decimal | None
    status: str
    broker_order_id: str | None
    trading_mode: str
    filled_quantity: int
    avg_fill_price: Decimal | None
    created_at: datetime
    updated_at: datetime


class OrderDetail(OrderResponse):
    fills: list[FillResponse]


class OrderListResponse(BaseModel):
    count: int
    orders: list[OrderResponse]


class PositionResponse(BaseModel):
    symbol: str
    quantity: int
    avg_cost: Decimal
    realized_pnl: Decimal
    mark_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None


class AccountResponse(BaseModel):
    account: str
    as_of: datetime
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    gross_exposure: Decimal
    position_count: int
    positions: list[PositionResponse]


class SubmitOrderResponse(BaseModel):
    order_id: str
    status: str
    message: str
    reference_price: Decimal | None
    decision: RiskDecision
    fill: FillResponse | None
    position: PositionResponse | None


class BriefStance(BaseModel):
    symbol: str
    name: str
    kind: str
    label: str
    risk_note: str | None = None


class BriefResponse(BaseModel):
    as_of: datetime
    generated_by: str
    agent_count: int
    direction: str
    confidence: float
    regime: str
    headline: str
    brief: str
    stances: list[BriefStance]


class OrgDeskInfo(BaseModel):
    key: str
    title: str
    tier: str
    weight: float
    lead: str
    members: list[str]


class OrgResponse(BaseModel):
    desks: list[OrgDeskInfo]
    tiers: list[str]
    agent_count: int


class AuditLogEntry(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    created_at: datetime


class AuditLogPage(BaseModel):
    count: int
    limit: int
    offset: int
    items: list[AuditLogEntry]
