# KOSPI-WATCHER — Data Dictionary

This document is the authoritative reference for every persisted column, enumeration,
domain schema, and API DTO in KOSPI-WATCHER. It is generated from, and must remain in
exact agreement with, the source code. When a model changes, update this file in the
same commit.

Source files of record:

- `src/kospi_watcher/db/models.py` — the nine ORM tables
- `src/kospi_watcher/db/types.py` — `DecimalString`
- `src/kospi_watcher/domain/money.py` — `DecimalNoFloat`, `to_decimal`, `reject_float`
- `src/kospi_watcher/domain/enums.py` — all enumerations
- `src/kospi_watcher/domain/agents/schemas.py` — `Evidence`, `AgentFinding`, `AgentRun`
- `src/kospi_watcher/domain/risk/schemas.py` — `OrderProposal`, `RiskLimits`, `RiskCheckResult`, `RiskDecision`
- `src/kospi_watcher/domain/execution/broker.py` — `ApprovedOrder`, `BrokerOrder`
- `src/kospi_watcher/domain/execution/paper.py` — `Fill`
- `src/kospi_watcher/domain/execution/position.py` — `PositionState`
- `src/kospi_watcher/infrastructure/marketdata/base.py` — `Quote`
- `src/kospi_watcher/config.py` — `Settings` (market-data / agent runtime settings)
- `src/kospi_watcher/api/schemas/requests.py`, `responses.py` — API DTOs
- `config/instruments.yml`, `config/risk_limits.yml` — seed / configuration data

---

## 1. Conventions

These rules apply uniformly across the schema and explain why certain SQLAlchemy types
were chosen.

- **Decimal-only money, stored as TEXT.** Every monetary or price value is a Python
  `Decimal`, never a `float`. In the database it is persisted through the custom
  `DecimalString` type (`db/types.py`), which is backed by `String`/TEXT and stores the
  canonical string form of the `Decimal`. This preserves precision identically on SQLite
  (local / CI) and Postgres (prod), and avoids SQLite's float-backed `NUMERIC`, which
  would silently round KRW amounts (refines ADR-008).
- **`float` is rejected at the boundary.** Pydantic monetary fields use
  `DecimalNoFloat = Annotated[Decimal, BeforeValidator(reject_float)]`. Passing a raw
  `float` raises `TypeError` at validation time; only `Decimal`, `int`, or a numeric
  string are accepted (`domain/money.py`). The same guard lives in `to_decimal()`.
- **Timezone-aware UTC timestamps.** All datetime columns are
  `DateTime(timezone=True)` and store UTC. Pydantic datetime fields are typed
  `AwareDatetime`, which rejects naive datetimes and enforces point-in-time discipline.
- **Enums persisted by string VALUE.** Every enum is a `StrEnum`; the stable
  wire/storage representation is the member's *string value*, never its integer
  position. Enum columns are plain `String(n)` holding that value.
- **Generic JSON, not JSONB.** List/dict columns use the dialect-agnostic `JSON` type
  (no Postgres `JSONB`, no native UUID). A single Alembic migration therefore covers
  both SQLite and Postgres (ADR-012).
- **Identifier widths.** Primary-key and foreign-key string identifiers are
  `String(64)`; symbols are `String(32)`; idempotency keys are `String(128)`.

---

## 2. Database tables

Nine tables, defined in `db/models.py`. "Null?" reflects the column's nullability
(`nullable=True` or an `Optional` mapping → Yes; otherwise No / NOT NULL). Tables
§2.1–§2.5 and §2.9 are created by migration `0001`; the paper-execution tables
§2.6 (`orders`), §2.7 (`fills`), and §2.8 (`positions`) are added by migration
`0002_paper_trading.py`.

### 2.1 `instruments` (`Instrument`)

The tradable/observable universe. Seeded from `config/instruments.yml`.

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `symbol` | `String(32)` | No | PK | Instrument code (e.g. `069500`, `KOSPI`). |
| `name` | `String(128)` | No | | Display name. |
| `instrument_type` | `String(16)` | No | | `InstrumentType` value. |
| `market` | `String(16)` | No | | `MarketCode` value. |
| `tradable` | `Boolean` | No | | `default=False`. True only for tradable instruments. |
| `created_at` | `DateTime(timezone=True)` | No | | UTC creation timestamp. |

### 2.2 `agent_runs` (`AgentRunRow`)

One row per agent invocation.

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `id` | `String(64)` | No | PK | Run identifier. |
| `agent_name` | `String(128)` | No | Index | Indexed for lookup by agent. |
| `agent_version` | `String(32)` | No | | |
| `status` | `String(16)` | No | | `AgentRunStatus` value. |
| `started_at` | `DateTime(timezone=True)` | No | | UTC. |
| `finished_at` | `DateTime(timezone=True)` | Yes | | `nullable=True`; null while running. |
| `model_name` | `String(64)` | No | | |
| `prompt_version` | `String(64)` | No | | |
| `error` | `Text` | Yes | | `nullable=True`; populated on failure. |
| `created_at` | `DateTime(timezone=True)` | No | | UTC. |

### 2.3 `agent_findings` (`AgentFindingRow`)

The versioned analytical output of an agent run.

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `id` | `String(64)` | No | PK | Finding identifier. |
| `run_id` | `String(64)` | No | FK → `agent_runs.id`, Index | Owning run. |
| `agent_name` | `String(128)` | No | Index | |
| `agent_version` | `String(32)` | No | | |
| `schema_version` | `String(16)` | No | | `AgentFinding` schema version (currently `1.0.0`). |
| `as_of` | `DateTime(timezone=True)` | No | | Point-in-time the finding applies to (UTC). |
| `horizon` | `String(16)` | No | | `Horizon` value. |
| `direction` | `String(16)` | No | | `MarketDirection` value. |
| `impact` | `String(16)` | No | | `Impact` value. |
| `confidence` | `Float` | No | | 0.0–1.0 (enforced by the Pydantic model). |
| `thesis` | `Text` | No | | |
| `evidence` | `JSON` | No | | `default=list`; list of `Evidence` dicts. |
| `counterevidence` | `JSON` | No | | `default=list`; list of `Evidence` dicts. |
| `affected_sectors` | `JSON` | No | | `default=list`; list of strings. |
| `affected_symbols` | `JSON` | No | | `default=list`; list of strings. |
| `invalidation_conditions` | `JSON` | No | | `default=list`; list of strings. |
| `data_quality` | `String(16)` | No | | `DataQuality` value. |
| `model_name` | `String(64)` | No | | |
| `prompt_version` | `String(64)` | No | | |
| `created_at` | `DateTime(timezone=True)` | No | | UTC. |

### 2.4 `risk_decisions` (`RiskDecisionRow`)

The Risk Engine's verdict for a proposal.

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `id` | `String(64)` | No | PK | Decision identifier. |
| `proposal_id` | `String(64)` | No | Index | The evaluated proposal. |
| `status` | `String(16)` | No | | `RiskDecisionStatus` value. |
| `reason` | `Text` | No | | Human-readable summary. |
| `requires_human` | `Boolean` | No | | `default=False`. |
| `checks` | `JSON` | No | | `default=list`; list of `RiskCheckResult` dicts. |
| `failed_checks` | `JSON` | No | | `default=list`; list of `RiskCheckCode` values. |
| `created_at` | `DateTime(timezone=True)` | No | | UTC. |

### 2.5 `order_proposals` (`OrderProposalRow`)

A proposed order. Carries no authority to trade until risk-approved.

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `id` | `String(64)` | No | PK | Proposal identifier. |
| `symbol` | `String(32)` | No | Index | |
| `instrument_type` | `String(16)` | No | | `InstrumentType` value. |
| `side` | `String(8)` | No | | `OrderSide` value. |
| `order_type` | `String(8)` | No | | `OrderType` value. |
| `quantity` | `Integer` | No | | Positive (enforced by the Pydantic model, `gt=0`). |
| `limit_price` | `DecimalString(32)` | Yes | | `nullable=True`; required for LIMIT orders. |
| `reference_price` | `DecimalString(32)` | Yes | | `nullable=True`. |
| `strategy_id` | `String(64)` | No | | |
| `strategy_version` | `String(32)` | No | | |
| `idempotency_key` | `String(128)` | No | **UNIQUE**, Index | Enforces single-submission; duplicate keys are rejected. |
| `rationale` | `Text` | Yes | | `nullable=True`. |
| `status` | `String(24)` | No | | `default="PROPOSED"`; an `OrderStatus` value. |
| `created_at` | `DateTime(timezone=True)` | No | | UTC. |

### 2.6 `orders` (`OrderRow`)

A paper order and its lifecycle (migration `0002`). `status` holds the current
`OrderStatus` value; legal transitions are enforced in `domain.execution.order_state`.

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `id` | `String(64)` | No | PK | Order identifier. |
| `proposal_id` | `String(64)` | No | Index | The originating proposal. |
| `risk_decision_id` | `String(64)` | Yes | | `nullable=True`; the approving `RiskDecision`. |
| `symbol` | `String(32)` | No | Index | |
| `instrument_type` | `String(16)` | No | | `InstrumentType` value. |
| `side` | `String(8)` | No | | `OrderSide` value. |
| `order_type` | `String(8)` | No | | `OrderType` value. |
| `quantity` | `Integer` | No | | |
| `limit_price` | `DecimalString(32)` | Yes | | `nullable=True`. |
| `status` | `String(24)` | No | Index | `OrderStatus` value. |
| `broker_order_id` | `String(64)` | Yes | | `nullable=True`; `PAPER-…` once submitted. |
| `idempotency_key` | `String(128)` | No | **UNIQUE**, Index | Single-submission guard. |
| `trading_mode` | `String(16)` | No | | `TradingMode` value (`PAPER`). |
| `filled_quantity` | `Integer` | No | | `default=0`. |
| `avg_fill_price` | `DecimalString(32)` | Yes | | `nullable=True`. |
| `created_at` | `DateTime(timezone=True)` | No | | UTC. |
| `updated_at` | `DateTime(timezone=True)` | No | | UTC; advanced on each transition. |

### 2.7 `fills` (`FillRow`)

One simulated execution against a paper order (migration `0002`).

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `id` | `String(64)` | No | PK | Fill identifier. |
| `order_id` | `String(64)` | No | FK → `orders.id`, Index | Owning order. |
| `symbol` | `String(32)` | No | Index | |
| `side` | `String(8)` | No | | `OrderSide` value. |
| `quantity` | `Integer` | No | | |
| `price` | `DecimalString(32)` | No | | Fill price (Decimal as TEXT). |
| `liquidity` | `String(16)` | No | | `"PAPER"` for simulated fills. |
| `created_at` | `DateTime(timezone=True)` | No | | UTC fill time. |

### 2.8 `positions` (`PositionRow`)

Per-`(account, symbol)` signed position with cost basis and realized PnL
(migration `0002`).

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `account` | `String(32)` | No | **PK (composite)** | `default="paper"`. |
| `symbol` | `String(32)` | No | **PK (composite)** | Together with `account` forms the primary key. |
| `quantity` | `Integer` | No | | `default=0`; signed (long > 0, short < 0). |
| `avg_cost` | `DecimalString(32)` | No | | `default=Decimal("0")`; per unit of `|quantity|`. |
| `realized_pnl` | `DecimalString(32)` | No | | `default=Decimal("0")`; cumulative. |
| `updated_at` | `DateTime(timezone=True)` | No | | UTC. |

### 2.9 `audit_logs` (`AuditLogRow`)

**Append-only** audit trail. Per ADR-006 the application has no update or delete path —
new rows only.

| Column | Type | Null? | Key/Index | Notes |
|---|---|---|---|---|
| `id` | `Integer` | No | PK, autoincrement | Surrogate key. |
| `action` | `String(48)` | No | Index | `AuditAction` value. |
| `entity_type` | `String(48)` | No | | The kind of entity affected. |
| `entity_id` | `String(64)` | Yes | | `nullable=True`. |
| `summary` | `Text` | No | | Human-readable description. |
| `payload` | `JSON` | Yes | | `nullable=True`; structured detail. |
| `created_at` | `DateTime(timezone=True)` | No | Index | UTC; indexed for time-range queries. |

---

## 3. Enumerations

All enums are `StrEnum` (`domain/enums.py`); the persisted/wire value is the member's
string value. `AgentRunStatus` lives in `domain/agents/schemas.py`.

| Enum | Purpose | Members (exact string values) |
|---|---|---|
| `TradingMode` | System operating mode; default `RESEARCH` (analysis only, no orders). | `RESEARCH`, `PAPER`, `GUARDED_LIVE`, `AUTO_LIVE` |
| `MarketCode` | Korean market / index code. | `KOSPI`, `KOSPI200`, `KOSDAQ` |
| `InstrumentType` | Instrument classification. | `INDEX`, `ETF`, `STOCK`, `FUTURE`, `OPTION` |
| `MarketDirection` | An agent's directional market view (not an order side). | `BULLISH`, `BEARISH`, `NEUTRAL` |
| `Impact` | How market-moving a finding is, independent of confidence. | `LOW`, `MEDIUM`, `HIGH` |
| `Horizon` | Forecast horizon for a finding. | `INTRADAY`, `D1`, `D5`, `D20`, `STRUCTURAL` |
| `DataQuality` | Quality of the data behind a finding. | `OK`, `PARTIAL`, `STALE`, `UNAVAILABLE` |
| `SourceType` | Type of an evidence source backing an agent claim. | `NEWS`, `DISCLOSURE`, `MACRO_RELEASE`, `PRICE_DATA`, `FLOW_DATA`, `RESEARCH_NOTE`, `REGULATORY`, `OTHER` |
| `MarketRegime` | The nine market-regime classes (PRODUCT_SPEC §2). | `RISK_ON_STRONG`, `RISK_ON_FRAGILE`, `LIQUIDITY_RALLY`, `EARNINGS_RALLY`, `SIDEWAYS_LOW_VOL`, `SIDEWAYS_HIGH_VOL`, `RISK_OFF`, `CRISIS`, `DATA_UNCERTAIN` |
| `OrderSide` | Buy or sell. | `BUY`, `SELL` |
| `OrderType` | Order pricing type. | `MARKET`, `LIMIT` |
| `OrderStatus` | The 13 order lifecycle states; legal transitions enforced in `domain.execution.order_state`. | `PROPOSED`, `RISK_REJECTED`, `RISK_APPROVED`, `AWAITING_HUMAN`, `APPROVED`, `SUBMITTING`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCEL_PENDING`, `CANCELLED`, `REJECTED`, `RECONCILIATION_ERROR` |
| `RiskDecisionStatus` | Outcome of a deterministic Risk Engine evaluation; deny-by-default. | `APPROVED`, `REJECTED` |
| `RiskCheckCode` | The 22 deterministic risk checks (TRADING_SAFETY.md); a rejected check appears in `RiskDecision.failed_checks`. | `INSTRUMENT_ALLOWED`, `STRATEGY_ALLOWED`, `MARKET_OPEN`, `DATA_FRESHNESS`, `QUOTE_FRESHNESS`, `PRICE_DEVIATION`, `MAX_ORDER_NOTIONAL`, `MAX_POSITION`, `MAX_GROSS_EXPOSURE`, `DAILY_LOSS_LIMIT`, `MAX_DRAWDOWN`, `STRATEGY_LOSS_LIMIT`, `DAILY_TRADE_COUNT`, `SLIPPAGE_LIMIT`, `OPEN_ORDER_COUNT`, `RECONCILIATION_STATE`, `DUPLICATE_ORDER`, `VOLATILITY_SPIKE`, `API_FAILURE`, `DATA_RELIABILITY`, `ETF_DISCOUNT_PREMIUM`, `INAV_ANOMALY` |
| `KillSwitchTrigger` | The 8 conditions that must ultimately trip the Kill Switch. | `RECONCILIATION_MISMATCH`, `DUPLICATE_ORDER`, `DAILY_LOSS_LIMIT`, `PRICE_DATA_DELAY`, `BROKER_API_ERRORS`, `ABNORMAL_ORDER_QUANTITY`, `STRATEGY_VERSION_MISMATCH`, `OPERATOR_EMERGENCY_STOP` |
| `AuditAction` | Audit-log action categories for important state changes. | `AGENT_RUN`, `ORDER_PROPOSAL_VALIDATED`, `RISK_EVALUATED`, `ORDER_STATE_TRANSITION`, `KILL_SWITCH`, `CONFIG_CHANGE` |
| `AgentRunStatus` | Lifecycle status of an `AgentRun` (defined in `agents/schemas.py`). | `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED` |

---

## 4. Domain schemas (Pydantic / wire contracts)

All domain models set `extra="forbid"` (unknown fields are rejected). `AwareDatetime`
fields reject naive datetimes. Monetary fields use `DecimalNoFloat`, which rejects raw
`float` inputs at validation time.

### 4.1 `Evidence` (`agents/schemas.py`)

A single sourced claim backing (or opposing) a finding. `extra="forbid"`.

| Field | Type | Constraints | Required |
|---|---|---|---|
| `source_id` | `str` | `min_length=1`; a claim without a `source_id` is excluded from scoring | Yes |
| `source_type` | `SourceType` | enum value | Yes |
| `title` | `str` | | Yes |
| `url` | `str \| None` | default `None` | No |
| `published_at` | `AwareDatetime` | timezone-aware | Yes |
| `available_at` | `AwareDatetime` | timezone-aware | Yes |
| `claim` | `str` | | Yes |

### 4.2 `AgentFinding` (`agents/schemas.py`)

The versioned output contract for every analysis agent. `extra="forbid"`.
Constant: `AGENT_FINDING_SCHEMA_VERSION = "1.0.0"`.

| Field | Type | Constraints / default | Required |
|---|---|---|---|
| `schema_version` | `str` | default = `AGENT_FINDING_SCHEMA_VERSION` (`"1.0.0"`) | No |
| `agent_name` | `str` | | Yes |
| `agent_version` | `str` | | Yes |
| `as_of` | `AwareDatetime` | timezone-aware | Yes |
| `horizon` | `Horizon` | enum value | Yes |
| `direction` | `MarketDirection` | enum value | Yes |
| `impact` | `Impact` | enum value | Yes |
| `confidence` | `float` | `ge=0.0`, `le=1.0` | Yes |
| `thesis` | `str` | | Yes |
| `evidence` | `list[Evidence]` | `default_factory=list` | No |
| `counterevidence` | `list[Evidence]` | `default_factory=list` | No |
| `affected_sectors` | `list[str]` | `default_factory=list` | No |
| `affected_symbols` | `list[str]` | `default_factory=list` | No |
| `invalidation_conditions` | `list[str]` | `default_factory=list` | No |
| `data_quality` | `DataQuality` | enum value | Yes |
| `model_name` | `str` | | Yes |
| `prompt_version` | `str` | | Yes |
| `created_at` | `AwareDatetime` | timezone-aware | Yes |

Property: `is_scorable` — `True` only if at least one evidence item carries a `source_id`.

### 4.3 `AgentRun` (`agents/schemas.py`)

An execution record for one agent invocation. `extra="forbid"`.

| Field | Type | Constraints / default | Required |
|---|---|---|---|
| `run_id` | `str` | | Yes |
| `agent_name` | `str` | | Yes |
| `agent_version` | `str` | | Yes |
| `status` | `AgentRunStatus` | enum value | Yes |
| `started_at` | `AwareDatetime` | timezone-aware | Yes |
| `finished_at` | `AwareDatetime \| None` | default `None` | No |
| `model_name` | `str` | | Yes |
| `prompt_version` | `str` | | Yes |
| `findings` | `list[AgentFinding]` | `default_factory=list` | No |
| `error` | `str \| None` | default `None` | No |

### 4.4 `OrderProposal` (`risk/schemas.py`)

A proposed order produced upstream; carries no authority to trade. `extra="forbid"`.

| Field | Type | Constraints / default | Required |
|---|---|---|---|
| `proposal_id` | `str` | | Yes |
| `created_at` | `AwareDatetime` | timezone-aware | Yes |
| `symbol` | `str` | | Yes |
| `instrument_type` | `InstrumentType` | enum value | Yes |
| `side` | `OrderSide` | enum value | Yes |
| `order_type` | `OrderType` | enum value | Yes |
| `quantity` | `int` | `gt=0` | Yes |
| `limit_price` | `DecimalNoFloat \| None` | default `None`; rejects `float` | No* |
| `reference_price` | `DecimalNoFloat \| None` | default `None`; rejects `float` | No |
| `strategy_id` | `str` | | Yes |
| `strategy_version` | `str` | | Yes |
| `idempotency_key` | `str` | `min_length=1` | Yes |
| `rationale` | `str \| None` | default `None` | No |

\* Model validator `_require_limit_price`: when `order_type is LIMIT`, `limit_price`
must be provided (else `ValueError`).
Property `effective_price`: returns `limit_price` if set, otherwise `reference_price`
(used for notional/deviation checks).

### 4.5 `RiskLimits` (`risk/schemas.py`)

Operator-controlled limits loaded from `config/risk_limits.yml`. `extra="forbid"`.
**Empty allow-lists mean "deny everything" — that is the intended default.** All
monetary defaults are `Decimal("0")`, i.e. block-everything until configured.

| Field | Type | Default | Notes |
|---|---|---|---|
| `version` | `int` | `1` | |
| `allowed_instruments` | `frozenset[str]` | `frozenset()` | Empty → no instrument is allowed. |
| `allowed_strategies` | `frozenset[str]` | `frozenset()` | Empty → no strategy is allowed. |
| `market_open` | `bool` | `False` | Market is closed unless explicitly opened. |
| `max_order_notional` | `DecimalNoFloat` | `Decimal("0")` | Per-order notional cap (KRW). |
| `max_order_quantity` | `int` | `0` | Per-order quantity cap. |
| `max_position_notional` | `DecimalNoFloat` | `Decimal("0")` | Per-instrument position cap (KRW). |
| `max_gross_exposure` | `DecimalNoFloat` | `Decimal("0")` | Total gross exposure cap (KRW). |
| `price_deviation_pct` | `DecimalNoFloat` | `Decimal("0")` | Max limit-price deviation from last (%). |
| `daily_loss_limit` | `DecimalNoFloat` | `Decimal("0")` | Daily realized loss limit (KRW). |
| `max_drawdown_pct` | `DecimalNoFloat` | `Decimal("0")` | Max drawdown (%). |
| `daily_trade_count` | `int` | `0` | Max trades per day. |
| `max_open_orders` | `int` | `0` | Max concurrent open orders. |
| `slippage_limit_pct` | `DecimalNoFloat` | `Decimal("0")` | Slippage limit (%). |

### 4.6 `RiskCheckResult` (`risk/schemas.py`)

Outcome of one deterministic risk check. `extra="forbid"`.

| Field | Type | Constraints | Required |
|---|---|---|---|
| `code` | `RiskCheckCode` | enum value | Yes |
| `passed` | `bool` | | Yes |
| `detail` | `str` | | Yes |

### 4.7 `RiskDecision` (`risk/schemas.py`)

The Risk Engine's verdict. An `ApprovedOrder` cannot be created unless
`status is APPROVED`. `extra="forbid"`.

| Field | Type | Constraints / default | Required |
|---|---|---|---|
| `decision_id` | `str` | | Yes |
| `proposal_id` | `str` | | Yes |
| `status` | `RiskDecisionStatus` | enum value | Yes |
| `created_at` | `AwareDatetime` | timezone-aware | Yes |
| `checks` | `list[RiskCheckResult]` | `default_factory=list` | No |
| `failed_checks` | `list[RiskCheckCode]` | `default_factory=list` | No |
| `reason` | `str` | | Yes |
| `requires_human` | `bool` | default `False` | No |

Property `approved`: `True` iff `status is RiskDecisionStatus.APPROVED`.

### 4.8 `ApprovedOrder` (`execution/broker.py`)

An order authorised for submission. `extra="forbid"`, **`frozen=True`** (immutable).
Construct only via `from_decision(proposal, decision, *, order_id=None)`, which raises
`ApprovedOrderError` unless `decision.status is APPROVED` and
`decision.proposal_id == proposal.proposal_id`.

| Field | Type | Constraints | Required |
|---|---|---|---|
| `order_id` | `str` | | Yes |
| `proposal_id` | `str` | | Yes |
| `risk_decision_id` | `str` | | Yes |
| `symbol` | `str` | | Yes |
| `side` | `OrderSide` | enum value | Yes |
| `order_type` | `OrderType` | enum value | Yes |
| `quantity` | `int` | `gt=0` | Yes |
| `limit_price` | `DecimalNoFloat \| None` | default `None`; rejects `float` | No |
| `idempotency_key` | `str` | `min_length=1` | Yes |
| `approved_at` | `AwareDatetime` | timezone-aware | Yes |

### 4.9 `BrokerOrder` (`execution/broker.py`)

A broker's acknowledgement of a submitted order. `extra="forbid"`.

| Field | Type | Constraints | Required |
|---|---|---|---|
| `broker_order_id` | `str` | | Yes |
| `status` | `OrderStatus` | enum value | Yes |
| `idempotency_key` | `str` | | Yes |
| `accepted_at` | `AwareDatetime` | timezone-aware | Yes |

> `MockBrokerAdapter` (mode `"MOCK"`) places **no real orders** and raises
> `DuplicateOrderError` if an already-seen `idempotency_key` is resubmitted. Submitted
> mock orders are returned with `status = OrderStatus.SUBMITTED` and a `MOCK-…`
> `broker_order_id`. Banner: `MOCK BROKER — NO REAL ORDERS, NOT REAL MARKET DATA`.

### 4.10 `Fill` (`execution/paper.py`)

A simulated execution against a paper order, produced by
`PaperBrokerAdapter.simulate_fill`. `extra="forbid"`. The paper broker places **no
real orders** and moves **no real money**; banner:
`PAPER BROKER — SIMULATED FILLS, NO REAL ORDERS, NO REAL MONEY`.

| Field | Type | Constraints / default | Required |
|---|---|---|---|
| `fill_id` | `str` | | Yes |
| `order_id` | `str` | | Yes |
| `symbol` | `str` | | Yes |
| `side` | `OrderSide` | enum value | Yes |
| `quantity` | `int` | `gt=0` | Yes |
| `price` | `DecimalNoFloat` | rejects `float` | Yes |
| `liquidity` | `str` | default `"PAPER"` | No |
| `filled_at` | `AwareDatetime` | timezone-aware | Yes |

### 4.11 `PositionState` (`execution/position.py`)

A pure, frozen dataclass holding signed position + cost basis + realized PnL.
**Not** a Pydantic model — all arithmetic is `Decimal` only (ADR-008). `apply_fill`
is a pure function `(state, side, quantity, price) -> PositionState`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `quantity` | `int` | `0` | Signed (long > 0, short < 0). |
| `avg_cost` | `Decimal` | `Decimal("0")` | Per unit of `|quantity|`; 0 when flat. |
| `realized_pnl` | `Decimal` | `Decimal("0")` | Cumulative realized PnL. |

Methods: `unrealized_pnl(mark_price)` = `(mark_price - avg_cost) * quantity`;
`market_value(mark_price)` = `mark_price * quantity`.

### 4.12 `Quote` (`infrastructure/marketdata/base.py`)

A point-in-time price for one instrument, returned by any `MarketDataProvider`.
`extra="forbid"`. Providers **never raise** — they return `None` / omit a symbol on
failure. Internal symbols: `KNOWN_SYMBOLS = ("069500", "102110", "229200", "KOSPI",
"USDKRW")`.

| Field | Type | Constraints / default | Required |
|---|---|---|---|
| `symbol` | `str` | | Yes |
| `price` | `DecimalNoFloat` | rejects `float` | Yes |
| `currency` | `str` | | Yes |
| `as_of` | `AwareDatetime` | timezone-aware | Yes |
| `source` | `str` | `"yahoo"` or `"mock"` | Yes |
| `stale` | `bool` | default `False` | No |

---

## 5. API request / response DTOs

Defined in `api/schemas/requests.py` and `api/schemas/responses.py`. Request models set
`extra="forbid"`. Price fields on requests are typed `Decimal` (lenient at the boundary:
JSON numbers are coerced), then pass through `DecimalNoFloat` when converted to the
domain `OrderProposal`, so no `float` reaches the domain money path.

### 5.1 Requests

#### `MockRunRequest`

| Field | Type | Default | Required |
|---|---|---|---|
| `agent_name` | `str` | | Yes |
| `universe` | `list[str]` | `default_factory=list` | No |

#### `OrderProposalRequest`

| Field | Type | Constraints / default | Required |
|---|---|---|---|
| `symbol` | `str` | | Yes |
| `instrument_type` | `InstrumentType` | enum value | Yes |
| `side` | `OrderSide` | enum value | Yes |
| `order_type` | `OrderType` | enum value | Yes |
| `quantity` | `int` | `gt=0` | Yes |
| `limit_price` | `Decimal \| None` | default `None` | No* |
| `reference_price` | `Decimal \| None` | default `None` | No |
| `strategy_id` | `str` | | Yes |
| `strategy_version` | `str` | default `"0.1.0"` | No |
| `idempotency_key` | `str` | `min_length=1` | Yes |
| `rationale` | `str \| None` | default `None` | No |

\* Model validator `_require_limit_price`: LIMIT orders require `limit_price`. Method
`to_domain()` builds an `OrderProposal` with a generated `proposal_id` and `created_at`.

#### `RiskEvaluateRequest`

| Field | Type | Default | Required |
|---|---|---|---|
| `proposal` | `OrderProposalRequest` | | Yes |
| `market_open` | `bool` | `True` | No |
| `last_price` | `Decimal \| None` | `None` | No |
| `position_notional` | `Decimal` | `Decimal("0")` | No |
| `gross_exposure` | `Decimal` | `Decimal("0")` | No |
| `daily_realized_loss` | `Decimal` | `Decimal("0")` | No |
| `open_orders` | `int` | `0` | No |
| `daily_trade_count` | `int` | `0` | No |

#### `SubmitOrderRequest`

Submit a proposal for **paper** execution (risk-gated, simulated fill). `extra="forbid"`.

| Field | Type | Default | Required |
|---|---|---|---|
| `proposal` | `OrderProposalRequest` | | Yes |
| `market_open` | `bool` | `True` | No |
| `last_price` | `Decimal \| None` | `None` | No |

### 5.2 Responses

Only declared fields are serialised; secrets are never part of any response schema.

#### `DbHealth`

| Field | Type |
|---|---|
| `connected` | `bool` |
| `backend` | `str` |

#### `RedisHealth`

| Field | Type |
|---|---|
| `backend` | `str` |
| `connected` | `bool` |
| `detail` | `str` |

#### `HealthResponse`

| Field | Type |
|---|---|
| `status` | `str` |
| `app` | `str` |
| `version` | `str` |
| `database` | `DbHealth` |
| `redis` | `RedisHealth` |
| `trading_mode` | `str` |
| `live_trading_enabled` | `bool` |
| `auto_execution_enabled` | `bool` |

#### `DataSourceStatus`

| Field | Type |
|---|---|
| `name` | `str` |
| `status` | `str` |

#### `SystemStatusResponse`

| Field | Type |
|---|---|
| `app` | `str` |
| `version` | `str` |
| `environment` | `str` |
| `server_time_utc` | `datetime` |
| `server_time_kst` | `datetime` |
| `trading_mode` | `str` |
| `feature_flags` | `dict[str, bool]` |
| `data_sources` | `list[DataSourceStatus]` |
| `agent_count` | `int` |
| `agent_runtime` | `str` |

> `feature_flags` carries `live_trading_enabled`, `auto_execution_enabled`,
> `live_execution_implemented` (`False`), and `paper_execution_implemented`
> (`True`). `agent_runtime` is `"llm"` only when `agent_runtime="llm"` **and** an
> `ANTHROPIC_API_KEY` is set, else `"mock"`.

#### `MarketQuote`

| Field | Type |
|---|---|
| `symbol` | `str` |
| `price` | `Decimal` |
| `currency` | `str` |
| `as_of` | `datetime` |
| `source` | `str` |
| `stale` | `bool` |

#### `MarketQuotesResponse`

| Field | Type |
|---|---|
| `provider` | `str` |
| `count` | `int` |
| `quotes` | `list[MarketQuote]` |

#### `AgentInfo`

| Field | Type |
|---|---|
| `name` | `str` |
| `version` | `str` |
| `category` | `str` |
| `summary` | `str` |
| `enabled` | `bool` |

#### `AgentListResponse`

| Field | Type |
|---|---|
| `count` | `int` |
| `agents` | `list[AgentInfo]` |

#### `ValidationResponse`

| Field | Type |
|---|---|
| `valid` | `bool` |
| `proposal_id` | `str` |
| `detail` | `str` |

#### `FillResponse`

| Field | Type |
|---|---|
| `id` | `str` |
| `symbol` | `str` |
| `side` | `str` |
| `quantity` | `int` |
| `price` | `Decimal` |
| `liquidity` | `str` |
| `created_at` | `datetime` |

#### `OrderResponse`

| Field | Type |
|---|---|
| `id` | `str` |
| `proposal_id` | `str` |
| `risk_decision_id` | `str \| None` |
| `symbol` | `str` |
| `side` | `str` |
| `order_type` | `str` |
| `quantity` | `int` |
| `limit_price` | `Decimal \| None` |
| `status` | `str` |
| `broker_order_id` | `str \| None` |
| `trading_mode` | `str` |
| `filled_quantity` | `int` |
| `avg_fill_price` | `Decimal \| None` |
| `created_at` | `datetime` |
| `updated_at` | `datetime` |

#### `OrderDetail` (extends `OrderResponse`)

| Field | Type |
|---|---|
| *(all `OrderResponse` fields)* | |
| `fills` | `list[FillResponse]` |

#### `OrderListResponse`

| Field | Type |
|---|---|
| `count` | `int` |
| `orders` | `list[OrderResponse]` |

#### `PositionResponse`

| Field | Type |
|---|---|
| `symbol` | `str` |
| `quantity` | `int` |
| `avg_cost` | `Decimal` |
| `realized_pnl` | `Decimal` |
| `mark_price` | `Decimal \| None` |
| `market_value` | `Decimal \| None` |
| `unrealized_pnl` | `Decimal \| None` |

#### `AccountResponse`

| Field | Type |
|---|---|
| `account` | `str` |
| `as_of` | `datetime` |
| `realized_pnl` | `Decimal` |
| `unrealized_pnl` | `Decimal` |
| `total_pnl` | `Decimal` |
| `gross_exposure` | `Decimal` |
| `position_count` | `int` |
| `positions` | `list[PositionResponse]` |

#### `SubmitOrderResponse`

| Field | Type |
|---|---|
| `order_id` | `str` |
| `status` | `str` |
| `message` | `str` |
| `reference_price` | `Decimal \| None` |
| `decision` | `RiskDecision` |
| `fill` | `FillResponse \| None` |
| `position` | `PositionResponse \| None` |

#### `AuditLogEntry`

| Field | Type |
|---|---|
| `id` | `int` |
| `action` | `str` |
| `entity_type` | `str` |
| `entity_id` | `str \| None` |
| `summary` | `str` |
| `created_at` | `datetime` |

#### `AuditLogPage`

| Field | Type |
|---|---|
| `count` | `int` |
| `limit` | `int` |
| `offset` | `int` |
| `items` | `list[AuditLogEntry]` |

> `RiskDecision` (§4.7) is reused directly as the response model for risk evaluation.

---

## 6. Seed / configuration data

### 6.1 Instrument universe (`config/instruments.yml`, `version: 1`)

Seeds the `instruments` table. Tradable ETFs must also appear in `risk_limits.yml`
`allowed_instruments` (deny-by-default).

| symbol | name | instrument_type | market | tradable |
|---|---|---|---|---|
| `KOSPI` | KOSPI Composite Index | `INDEX` | `KOSPI` | `false` |
| `KOSPI200` | KOSPI 200 Index | `INDEX` | `KOSPI200` | `false` |
| `KOSDAQ` | KOSDAQ Composite Index | `INDEX` | `KOSDAQ` | `false` |
| `069500` | KODEX 200 | `ETF` | `KOSPI200` | `true` |
| `102110` | TIGER 200 | `ETF` | `KOSPI200` | `true` |
| `229200` | KODEX KOSDAQ150 | `ETF` | `KOSDAQ` | `false` |

### 6.2 Risk limits (`config/risk_limits.yml`, `version: 1`) — deny-by-default

Only instruments and strategies listed here can ever be approved by the Risk Engine.
Monetary values are strings to preserve `Decimal` precision (KRW); `float` is forbidden.
Changes to this file are safety-relevant and must be recorded (ADR / change log) per
CLAUDE.md.

| Key | Value | Notes |
|---|---|---|
| `version` | `1` | |
| `allowed_instruments` | `["069500", "102110"]` | KODEX 200, TIGER 200 (KOSPI200-linked ETFs only). |
| `allowed_strategies` | `["baseline-momentum-v0", "mean-reversion-v0"]` | |
| `market_open` | `false` | Market treated CLOSED by default; callers must explicitly open it. |
| `max_order_notional` | `"50000000"` | 50,000,000 KRW per order. |
| `max_order_quantity` | `100000` | shares/units per order. |
| `max_position_notional` | `"100000000"` | 100,000,000 KRW per instrument. |
| `max_gross_exposure` | `"300000000"` | 300,000,000 KRW total. |
| `price_deviation_pct` | `"5"` | Reject if limit price deviates >5% from last. |
| `daily_loss_limit` | `"5000000"` | 5,000,000 KRW realized loss/day. |
| `max_drawdown_pct` | `"10"` | |
| `daily_trade_count` | `50` | |
| `max_open_orders` | `20` | |
| `slippage_limit_pct` | `"1"` | |

---

## 7. Application settings (`config.py` — selected)

`Settings` (pydantic-settings) is the process-wide config singleton. The rows below
cover the **market-data** and **agent-runtime** settings; the mandated trading-safety
defaults (`trading_mode=RESEARCH`, `live_trading_enabled=False`,
`auto_execution_enabled=False`) and secrets (`SecretStr`, never logged or returned) are
documented in ARCHITECTURE.md §6 and TRADING_SAFETY.md. Two module-level flags also live
in `config.py`: `PAPER_EXECUTION_IMPLEMENTED = True` and
`LIVE_EXECUTION_IMPLEMENTED = False`.

| Setting (env) | Type | Default | Notes |
|---|---|---|---|
| `agent_runtime` (`AGENT_RUNTIME`) | `str` | `"mock"` | `"mock"` = deterministic offline agents; `"llm"` = real Anthropic agents (used only when `ANTHROPIC_API_KEY` is set; else falls back to mock). |
| `agent_model` (`AGENT_MODEL`) | `str` | `"claude-opus-4-8"` | LLM model id; override to a cheaper tier (e.g. `claude-sonnet-4-6`) for high-volume runs. |
| `agent_max_tokens` (`AGENT_MAX_TOKENS`) | `int` | `2048` | Max output tokens for an LLM agent call. |
| `market_data_provider` (`MARKET_DATA_PROVIDER`) | `str` | `"yahoo"` | `"yahoo"` = real, keyless quotes; `"mock"` = offline. |
| `market_data_ttl_seconds` (`MARKET_DATA_TTL_SECONDS`) | `int` | `60` | Per-symbol quote cache TTL (seconds). |
| `market_data_user_agent` (`MARKET_DATA_USER_AGENT`) | `str` | a browser UA string | Sent as `User-Agent` to Yahoo (required, else HTTP 429). |
