"""Domain enumerations.

Every enum is a :class:`enum.StrEnum`, so the *string value* is the stable
wire/storage representation across SQLAlchemy (``Enum``/``String``) and Pydantic
/ JSON. Never persist the integer position of a member — only its value.
"""

from __future__ import annotations

from enum import StrEnum


class TradingMode(StrEnum):
    """System operating mode. Default is RESEARCH (analysis only, no orders)."""

    RESEARCH = "RESEARCH"
    PAPER = "PAPER"
    GUARDED_LIVE = "GUARDED_LIVE"
    AUTO_LIVE = "AUTO_LIVE"


class MarketCode(StrEnum):
    KOSPI = "KOSPI"
    KOSPI200 = "KOSPI200"
    KOSDAQ = "KOSDAQ"


class InstrumentType(StrEnum):
    INDEX = "INDEX"
    ETF = "ETF"
    STOCK = "STOCK"
    FUTURE = "FUTURE"
    OPTION = "OPTION"


class MarketDirection(StrEnum):
    """An agent's directional market view (not an order side)."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Impact(StrEnum):
    """How market-moving a finding is, independent of confidence."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Horizon(StrEnum):
    """Forecast horizon for a finding."""

    INTRADAY = "INTRADAY"
    D1 = "D1"
    D5 = "D5"
    D20 = "D20"
    STRUCTURAL = "STRUCTURAL"


class DataQuality(StrEnum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class SourceType(StrEnum):
    """Type of an evidence source backing an agent claim."""

    NEWS = "NEWS"
    DISCLOSURE = "DISCLOSURE"
    MACRO_RELEASE = "MACRO_RELEASE"
    PRICE_DATA = "PRICE_DATA"
    FLOW_DATA = "FLOW_DATA"
    RESEARCH_NOTE = "RESEARCH_NOTE"
    REGULATORY = "REGULATORY"
    OTHER = "OTHER"


class MarketRegime(StrEnum):
    """The nine market-regime classes (see PRODUCT_SPEC §2)."""

    RISK_ON_STRONG = "RISK_ON_STRONG"
    RISK_ON_FRAGILE = "RISK_ON_FRAGILE"
    LIQUIDITY_RALLY = "LIQUIDITY_RALLY"
    EARNINGS_RALLY = "EARNINGS_RALLY"
    SIDEWAYS_LOW_VOL = "SIDEWAYS_LOW_VOL"
    SIDEWAYS_HIGH_VOL = "SIDEWAYS_HIGH_VOL"
    RISK_OFF = "RISK_OFF"
    CRISIS = "CRISIS"
    DATA_UNCERTAIN = "DATA_UNCERTAIN"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(StrEnum):
    """The 13 order states. Allowed transitions are defined in
    ``domain.execution.order_state``; illegal transitions raise."""

    PROPOSED = "PROPOSED"
    RISK_REJECTED = "RISK_REJECTED"
    RISK_APPROVED = "RISK_APPROVED"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    APPROVED = "APPROVED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    RECONCILIATION_ERROR = "RECONCILIATION_ERROR"


class RiskDecisionStatus(StrEnum):
    """Outcome of a deterministic Risk Engine evaluation. Deny-by-default."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RiskCheckCode(StrEnum):
    """The 22 deterministic risk checks (see TRADING_SAFETY.md). A rejected
    check appears in ``RiskDecision.failed_checks``."""

    INSTRUMENT_ALLOWED = "INSTRUMENT_ALLOWED"
    STRATEGY_ALLOWED = "STRATEGY_ALLOWED"
    MARKET_OPEN = "MARKET_OPEN"
    DATA_FRESHNESS = "DATA_FRESHNESS"
    QUOTE_FRESHNESS = "QUOTE_FRESHNESS"
    PRICE_DEVIATION = "PRICE_DEVIATION"
    MAX_ORDER_NOTIONAL = "MAX_ORDER_NOTIONAL"
    MAX_POSITION = "MAX_POSITION"
    MAX_GROSS_EXPOSURE = "MAX_GROSS_EXPOSURE"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    STRATEGY_LOSS_LIMIT = "STRATEGY_LOSS_LIMIT"
    DAILY_TRADE_COUNT = "DAILY_TRADE_COUNT"
    SLIPPAGE_LIMIT = "SLIPPAGE_LIMIT"
    OPEN_ORDER_COUNT = "OPEN_ORDER_COUNT"
    RECONCILIATION_STATE = "RECONCILIATION_STATE"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    API_FAILURE = "API_FAILURE"
    DATA_RELIABILITY = "DATA_RELIABILITY"
    ETF_DISCOUNT_PREMIUM = "ETF_DISCOUNT_PREMIUM"
    INAV_ANOMALY = "INAV_ANOMALY"


class KillSwitchTrigger(StrEnum):
    """The 8 conditions that must ultimately trip the Kill Switch."""

    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    PRICE_DATA_DELAY = "PRICE_DATA_DELAY"
    BROKER_API_ERRORS = "BROKER_API_ERRORS"
    ABNORMAL_ORDER_QUANTITY = "ABNORMAL_ORDER_QUANTITY"
    STRATEGY_VERSION_MISMATCH = "STRATEGY_VERSION_MISMATCH"
    OPERATOR_EMERGENCY_STOP = "OPERATOR_EMERGENCY_STOP"


class AuditAction(StrEnum):
    """Audit-log action categories recorded for important state changes."""

    AGENT_RUN = "AGENT_RUN"
    ORDER_PROPOSAL_VALIDATED = "ORDER_PROPOSAL_VALIDATED"
    RISK_EVALUATED = "RISK_EVALUATED"
    ORDER_STATE_TRANSITION = "ORDER_STATE_TRANSITION"
    KILL_SWITCH = "KILL_SWITCH"
    CONFIG_CHANGE = "CONFIG_CHANGE"
