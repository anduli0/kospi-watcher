# KOSPI-WATCHER — System Architecture

Status: Phase 1. Verified against the source tree under
`src/kospi_watcher/`, `apps/`, `alembic/`, `pyproject.toml`, and `docker-compose.yml`.

Five capabilities are now live and described below: **real market data**
(keyless Yahoo Finance with a mock fallback, §4a), a **PAPER (simulated)
execution path** (the safe execution tier, §4b), **real LLM agents**
(Anthropic-backed, with a deterministic mock fallback, §4c), a **research-desk
hierarchy** that organises the 21 agents into 5 desks + a Chief across 3 tiers
(§4d), and a **market-prediction / daily-brief engine** that synthesises every
agent run into a single house view — regime, direction/confidence, long /
inverse / 곱버스 (leveraged-inverse) instrument stances, scenarios, and a Korean
narrative brief (§4e).

> **Product focus.** The product now centers on **prediction + a daily brief**
> (in line with the sibling Fed-Watcher / KRW-Watcher systems); the trading path
> is **secondary and paper-only** (PAPER simulated execution; live remains
> unimplemented). The prediction is a **deterministic synthesis** over the agent
> findings, so it is identical whether those findings came from the mock or the
> real-LLM runtime.

> Safety note carried through this document: **PAPER (simulated) execution is
> implemented and safe** — it moves no real money and contacts no real broker,
> and runs only when `TRADING_MODE=PAPER` (`PAPER_EXECUTION_IMPLEMENTED = True`).
> **Live order execution remains NOT implemented in this phase.**
> `LIVE_EXECUTION_IMPLEMENTED = False` in `src/kospi_watcher/config.py`, and the
> mandated trading-safety defaults (`TradingMode.RESEARCH`,
> `live_trading_enabled=False`, `auto_execution_enabled=False`) ship as the
> configured defaults.

---

## 1. System overview

KOSPI-WATCHER is a Korean equity (KOSPI) market analysis and risk-controlled
trading **research** platform. It runs a catalog of **21 analysis agents** that
**only analyze** — they emit structured findings and have no order authority
whatsoever (no submit surface is importable from the agent path). Every order
must pass through a single, **deterministic, deny-by-default Risk Engine**
(`src/kospi_watcher/domain/risk/engine.py`), which is the sole gate to any order:
no LLM, no I/O, pure rules over an `OrderProposal` plus a `RiskContext`. An
`ApprovedOrder` cannot even be constructed without an `APPROVED` `RiskDecision`.

A risk-approved proposal can be **executed against a simulated (PAPER) broker**:
`PaperBrokerAdapter` produces a deterministic fill, the order walks the 13-state
machine, and the fill folds into a signed position and realized PnL. This path
moves **no real money** and contacts **no real broker** — it runs only when
`TRADING_MODE=PAPER` (`PAPER_EXECUTION_IMPLEMENTED = True`). **Live execution is
not implemented in this phase** — the flag `LIVE_EXECUTION_IMPLEMENTED = False`
in `src/kospi_watcher/config.py` documents that flipping any env toggle cannot,
on its own, produce a real broker order; the only brokers are the simulated
`MockBrokerAdapter` and `PaperBrokerAdapter`, which place no real orders.

Market prices (KOSPI index, USD/KRW, the tradable KOSPI200 ETFs) are **live by
default** via a keyless Yahoo Finance provider, with a deterministic mock
fallback; the provider never raises, so the risk and trading paths degrade
safely. Analysis agents can run on a **real Anthropic LLM** (default model
`claude-opus-4-8`) or the deterministic mock — but agents still have **no order
authority** under either runtime.

---

## 2. Component map

Five services share one domain package (`kospi_watcher`). Backend services are
thin entrypoints under `apps/<svc>/main.py` that import the shared package
(ADR-011).

| Service | Code | Port | Responsibility |
|---|---|---|---|
| `api` | `src/kospi_watcher/api/app.py` (`create_app`) via `apps/api/main.py` | 8000 | Main FastAPI app. Health, system status, agent list / mock-run / LLM run, live market quotes, order-proposal validation, risk evaluation, **paper trading** (orders / positions / account), audit-log listing. Owns persistence + seeding on startup. |
| `agent-service` | `src/kospi_watcher/agent_service/app.py` via `apps/agent-service/main.py` | 8001 | Isolated ASGI app. **Analysis only**, no order-execution surface. Exposes `/health`, `/agents`, `/run`. |
| `execution-gateway` | `src/kospi_watcher/execution_gateway/app.py` via `apps/execution-gateway/main.py` | 8002 | Isolated ASGI app. **No public submit endpoint** in this phase — exposes only `/health`. The submit path is in-process; `ExecutionGateway` allows the simulated `MOCK` and `PAPER` brokers and blocks any live broker. |
| `worker` | `src/kospi_watcher/worker/scheduler.py` via `apps/worker/main.py` | — | APScheduler process: a `heartbeat` job (every 60s), a `mock_agent_sweep` job (every 15 min), and a `refresh_prediction` job (every 30 min) that runs all agents, synthesizes a fresh house prediction / daily brief, and persists it (§4e). Never creates orders. |
| `web` | `apps/web/` (Next.js App Router) | 3000 | Next.js 15 / React 19 front end. Reads `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`). |

The `api` service mounts nine routers (`src/kospi_watcher/api/app.py`):
`health` is mounted at the root; the other eight (`system`, `agents`,
`prediction`, `market`, `order_proposals`, `risk`, `trading`, `audit_logs`) are
mounted under `/api/v1`.

### The 18 `api` endpoints

| Method | Path | Route module |
|---|---|---|
| GET | `/health` | `api/routes/health.py` |
| GET | `/api/v1/system/status` | `api/routes/system.py` |
| GET | `/api/v1/agents` | `api/routes/agents.py` |
| POST | `/api/v1/agents/mock-run` | `api/routes/agents.py` |
| POST | `/api/v1/agents/run` | `api/routes/agents.py` |
| POST | `/api/v1/prediction/run` | `api/routes/prediction.py` |
| GET | `/api/v1/prediction/latest` | `api/routes/prediction.py` |
| GET | `/api/v1/brief` | `api/routes/prediction.py` |
| GET | `/api/v1/agents/org` | `api/routes/prediction.py` |
| GET | `/api/v1/market/quotes` | `api/routes/market.py` |
| POST | `/api/v1/order-proposals/validate` | `api/routes/order_proposals.py` |
| POST | `/api/v1/risk/evaluate` | `api/routes/risk.py` |
| POST | `/api/v1/orders` | `api/routes/trading.py` |
| GET | `/api/v1/orders` | `api/routes/trading.py` |
| GET | `/api/v1/orders/{order_id}` | `api/routes/trading.py` |
| GET | `/api/v1/positions` | `api/routes/trading.py` |
| GET | `/api/v1/account` | `api/routes/trading.py` |
| GET | `/api/v1/audit-logs` | `api/routes/audit_logs.py` |

`POST /api/v1/agents/run` runs the configured agent runtime (real LLM when armed,
else the mock); the four `prediction.py` endpoints expose the product's primary
surface — run/fetch the house prediction, the daily brief, and the desk org
chart (§4d, §4e); `GET /api/v1/market/quotes` returns live (or mock) quotes; the
five `trading.py` endpoints drive the secondary PAPER execution path (§4b).

CORS allows only `GET`/`POST`, origins from `cors_allow_origins`
(default `http://localhost:3000`), and credentials are disabled.

### Request flow and the execution isolation boundary

```
                        ┌──────────────────────────────────────────────────────┐
                        │                      api  (:8000)                     │
                        │                kospi_watcher.api.app                  │
   web (:3000) ──HTTP──▶│  routers: health, system, agents, prediction, market,│
   Next.js              │           order-proposals, risk, trading, audit-logs │
                        │                       │                              │
                        │        ┌──────────────┼───────────────┐              │
                        │        ▼              ▼               ▼              │
                        │   domain.agents   domain.risk    db (repositories /  │
                        │   (21 agents,     RiskEngine      ORM models /        │
                        │    analysis only) (deny-by-       audit_logs)         │
                        │        │           default)           │              │
                        └────────┼───────────────┼──────────────┼──────────────┘
                                 │               │              ▼
                                 │               │        SQLite / Postgres
                                 │               │
   agent-service (:8001) ◀───────┘               │   (analysis ASGI; no order surface)
   kospi_watcher.agent_service                   │
                                                 │
   ╔═════════════════════════════════════════════▼══════════════════════════════╗
   ║  ISOLATION BOUNDARY — execution-gateway (:8002)                             ║
   ║  kospi_watcher.execution_gateway.ExecutionGateway                           ║
   ║    • NO public submit endpoint (only /health)                              ║
   ║    • submit() is the ONLY caller of broker.submit_order outside the broker  ║
   ║    • broker ∈ {MockBrokerAdapter, PaperBrokerAdapter} → NO REAL ORDERS,     ║
   ║      NO REAL MONEY (PAPER requires PAPER_EXECUTION_IMPLEMENTED)             ║
   ║    • any LIVE broker blocked unless LIVE_EXECUTION_IMPLEMENTED and armed     ║
   ╚════════════════════════════════════════════════════════════════════════════╝
```

The PAPER submit path runs in-process through `TradingService.submit_order`
(`trading/service.py`), which orchestrates risk → approve → gateway → paper fill
→ position/PnL; see §4b.

The `domain/execution/__init__.py` docstring records the rule: `submit_order` is
defined only in `domain/execution/broker.py` and called only by the gateway; no
analysis-agent module imports the order path.

---

## 3. Layering

The backend is a single src-layout package, `kospi_watcher`, installed editable
(`pip install -e .`); the `apps/<svc>` directories are thin entrypoints
(ADR-011, src-layout).

```
src/kospi_watcher/
├── config.py                 # pydantic-settings; LIVE_EXECUTION_IMPLEMENTED flag
├── logging_config.py         # structlog config + secret redaction
├── domain/                   # PURE — no I/O, no app frameworks
│   ├── enums.py              # StrEnum domain enumerations
│   ├── time.py               # tz-aware UTC helpers (ADR-009)
│   ├── money.py              # Decimal-only money (ADR-008)
│   ├── agents/               # base, catalog (21 specs), org (5 desks + Chief), registry, schemas, llm_agent
│   ├── prediction/           # instruments (long/inverse ladder), regime, schemas, synthesizer
│   ├── risk/                 # engine, limits, schemas
│   └── execution/            # broker, order_state, paper, position
├── infrastructure/           # db engine/session, redis client, market data
│   ├── db.py
│   ├── redis_client.py
│   └── marketdata/           # base (Quote/Protocol), yahoo, mock, factory
├── db/                       # ORM models, repositories, alembic-backed schema
│   ├── models.py             # 10 tables
│   ├── types.py              # DecimalString TypeDecorator
│   ├── repositories.py
│   └── seed.py
├── api/                      # FastAPI app, routes, schemas, deps
├── agent_service/            # isolated analysis ASGI app + service (mock + llm)
├── execution_gateway/        # isolated gateway ASGI app + ExecutionGateway
├── trading/                  # TradingService — the paper-execution orchestrator
└── worker/                   # APScheduler jobs
```

**Dependency rule (inward toward `domain`):**

- `domain` depends on nothing app-specific — only the standard library and
  Pydantic. It performs no I/O and imports no FastAPI/SQLAlchemy/Redis.
- `infrastructure`, `db`, `api`, and the service apps all depend inward on
  `domain`. For example `db/types.py` imports `domain.money.to_decimal`;
  `db/repositories.py` maps `domain` schemas (`AgentRun`, `OrderProposal`,
  `RiskDecision`) onto ORM rows; `api/schemas/requests.py` converts request
  models into domain `OrderProposal` via `to_domain()`.
- Alembic migrations (`alembic/env.py`) also reflect `Base.metadata` from
  `infrastructure.db` and pull the URL from `config`.

---

## 4. Data flow for an order proposal

The order path is enforced by types so that no order can exist without an
approved risk decision. The actual sequence:

1. **Request → domain proposal.** `OrderProposalRequest` (`api/schemas/requests.py`)
   accepts JSON, then `to_domain()` builds a domain `OrderProposal`
   (`domain/risk/schemas.py`). The request's `Decimal` price fields pass through
   the domain's `DecimalNoFloat`, so no `float` ever reaches the money path.
   `POST /api/v1/order-proposals/validate` persists the proposal as `PROPOSED`
   and places **no order** (duplicate `idempotency_key` → HTTP 409).

2. **Risk evaluation.** `RiskEngine.evaluate(proposal, RiskContext)`
   (`domain/risk/engine.py`) runs the 22 deterministic checks from
   `RiskCheckCode`. Limits come from `config/risk_limits.yml` via
   `load_risk_limits()`; empty allow-lists mean *deny everything*. The engine
   is pure: no LLM, no I/O, no broker access. Checks that need live
   infrastructure not present in Phase 1 return a clearly labelled
   `[PLACEHOLDER]` pass and never gate-open a real order. `POST /api/v1/risk/evaluate`
   builds the `RiskContext` from request fields and the configured `trading_mode`.

3. **RiskDecision (deny-by-default).** The engine returns a `RiskDecision` with
   `status` `APPROVED` or `REJECTED` (`RiskDecisionStatus`). It is `APPROVED`
   only if `failed_checks` is empty — any failed check (or unhandled case)
   results in `REJECTED` (ADR-010). Under `TradingMode.GUARDED_LIVE`, an approved
   decision sets `requires_human=True` (never auto-sends).

4. **APPROVED → ApprovedOrder.** Only an `APPROVED` decision can build an
   `ApprovedOrder` via `ApprovedOrder.from_decision(proposal, decision)`
   (`domain/execution/broker.py`). The factory raises `ApprovedOrderError` if
   the decision is not `APPROVED` or does not belong to the proposal.
   `ApprovedOrder` is a frozen Pydantic model — the only object the gateway will
   submit.

5. **ExecutionGateway.submit().** `ExecutionGateway.submit(order)`
   (`execution_gateway/gateway.py`) is the only caller of `broker.submit_order`
   outside the broker module. A non-mock submission raises `GatewayBlockedError`
   unless `LIVE_EXECUTION_IMPLEMENTED and settings.live_execution_armed` — both
   are false in this phase.

6. **MockBrokerAdapter.** The default broker (`MockBrokerAdapter`) performs **no
   real orders**: it returns a synthetic `BrokerOrder` (`MOCK-…` id, status
   `SUBMITTED`) and raises `DuplicateOrderError` on a repeated `idempotency_key`.

**13-state order machine.** `domain/execution/order_state.py` defines
`ALLOWED_TRANSITIONS` over all 13 `OrderStatus` values
(`PROPOSED`, `RISK_REJECTED`, `RISK_APPROVED`, `AWAITING_HUMAN`, `APPROVED`,
`SUBMITTING`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCEL_PENDING`,
`CANCELLED`, `REJECTED`, `RECONCILIATION_ERROR`). A module-level assertion
guarantees the machine covers every status exactly once; terminal states
(`RISK_REJECTED`, `FILLED`, `CANCELLED`, `REJECTED`, `RECONCILIATION_ERROR`) have
no outgoing edges, and any illegal transition raises `IllegalTransitionError`.

---

## 4a. Market data (keyless Yahoo + mock fallback)

Market prices are served by a small provider abstraction in
`infrastructure/marketdata/`:

- **`base.py`** defines the `Quote` model (`symbol`, `price` as `DecimalNoFloat`,
  `currency`, `as_of` as `AwareDatetime`, `source` ∈ `{"yahoo","mock"}`, `stale`)
  and the `MarketDataProvider` `Protocol`. The protocol contract is explicit:
  implementations **must never raise** from `get_quote` / `get_quotes` — they
  return `None` / omit on failure so the risk and trading paths degrade safely.
  `KNOWN_SYMBOLS = ("069500", "102110", "229200", "KOSPI", "USDKRW")` are the
  internal symbols.
- **`yahoo.py` (`YahooMarketDataProvider`, `name="yahoo"`)** pulls live quotes
  from the public Yahoo Finance chart endpoint
  (`https://query1.finance.yahoo.com/v8/finance/chart/`) — **no API key**. A
  `User-Agent` header is sent (otherwise Yahoo answers HTTP 429). Internal
  symbols are mapped to Yahoo symbols: `069500→069500.KS`, `102110→102110.KS`,
  `229200→229200.KS`, `KOSPI→^KS11`, `USDKRW→KRW=X`. Results are cached for a
  short TTL (`market_data_ttl_seconds`, default 60s). On any error (HTTP non-200,
  transport error, parse failure) it returns the last cached value flagged
  `stale=True`, or `None` if nothing is cached — it never raises. The price is
  parsed as a `Decimal` via `to_decimal(str(price))` (no `float`, ADR-008). The
  `httpx.AsyncClient` is injectable for tests.
- **`mock.py` (`MockMarketDataProvider`, `name="mock"`)** returns fixed,
  clearly-labelled prices (`source="mock"`, `stale=True`) and never touches the
  network.
- **`factory.py`** (`get_market_data_provider`) selects the backend by the
  `market_data_provider` setting (`"yahoo"` default, else `"mock"`) and caches a
  process-wide singleton; `reset_market_data_provider()` disposes it for tests.

Settings (`config.py`): `market_data_provider` (`"yahoo"|"mock"`),
`market_data_ttl_seconds` (default 60), `market_data_user_agent`.

Consumers: `GET /api/v1/market/quotes` (`api/routes/market.py`) returns a
`MarketQuotesResponse` (`provider`, `count`, list of `MarketQuote`) for the
requested comma-separated symbols (defaulting to `KNOWN_SYMBOLS`). Risk
evaluation (`api/routes/risk.py`) now pulls a **live `last_price`**: it prefers
an explicit `last_price`, else a live quote, else the proposal's own
`effective_price`, so the deviation check always runs. The paper-trading path
(§4b) uses the same provider to mark positions and to price MARKET fills.
`/system/status` reports the active provider as a data source
(`market-data:<provider>`); the broker/disclosure/macro feeds remain unwired
placeholders.

---

## 4b. Paper execution (the safe execution tier)

A risk-approved proposal can be executed against a **simulated broker**. This
path moves **no real money** and contacts **no real broker**; it runs only when
`TRADING_MODE=PAPER`.

**Orchestrator — `TradingService.submit_order`** (`trading/service.py`) is the
one place that takes an `OrderProposal` all the way to a simulated fill:

```
OrderProposal ──▶ RiskEngine.evaluate ──▶ RiskDecision
   │                                          │
   │                          (REJECTED) ─────┴──▶ order → RISK_REJECTED (terminal)
   │
   │  (APPROVED)
   ▼
ApprovedOrder.from_decision ──▶ ExecutionGateway.submit ──▶ PaperBrokerAdapter
   │                                                              │ (BrokerOrder ack)
   ▼                                                              ▼
order walks: PROPOSED → RISK_APPROVED → APPROVED → SUBMITTING → SUBMITTED
   │
   ▼
PaperBrokerAdapter.simulate_fill ──▶ Fill ──▶ apply_fill ──▶ PositionState / realized PnL
   │
   ▼
order → FILLED (terminal); each transition is persisted + audit-logged
```

- **Gate.** `submit_order` raises `ExecutionDisabledError` (HTTP 409) unless
  `trading_mode` is `PAPER` — `RESEARCH` is analysis only, and the live modes are
  blocked because live execution is not implemented. Duplicate `idempotency_key`
  → `DuplicateOrderError` (409).
- **Risk first.** The Risk Engine runs exactly as in §4 (deny-by-default). A
  MARKET proposal is enriched with the live reference price (§4a) so the engine
  can size it; gross exposure / position notional are computed from existing
  positions.
- **PaperBrokerAdapter** (`domain/execution/paper.py`, `mode="PAPER"`) returns a
  synthetic `BrokerOrder` (`PAPER-…` id) and `simulate_fill(order, reference_price)`
  fully fills at the LIMIT price (LIMIT) or the reference price (MARKET), raising
  `PaperFillError` only if a MARKET order has no reference price. Banner:
  `PAPER BROKER — SIMULATED FILLS, NO REAL ORDERS, NO REAL MONEY`.
- **Gateway gating.** `ExecutionGateway.submit` (`execution_gateway/gateway.py`)
  allows `MOCK` and `PAPER` brokers (PAPER additionally requires
  `PAPER_EXECUTION_IMPLEMENTED`); any non-simulated (live) broker is blocked
  unless `LIVE_EXECUTION_IMPLEMENTED and live_execution_armed` — both false here.
- **Position & PnL math** (`domain/execution/position.py`) is pure `Decimal`
  (ADR-008): `PositionState` carries a *signed* `quantity`, `avg_cost` per unit
  of the absolute position, and cumulative `realized_pnl`. `apply_fill` is a pure
  function — increasing recomputes weighted-average cost; reducing realizes PnL on
  the closed quantity; a fill exceeding the position flips it and re-bases cost to
  the fill price.

**Endpoints** (`api/routes/trading.py`): `POST /api/v1/orders` (submit; 409 in
RESEARCH), `GET /api/v1/orders` (list), `GET /api/v1/orders/{order_id}` (detail +
fills), `GET /api/v1/positions` (marked to live quotes), `GET /api/v1/account`
(aggregate realized / unrealized / total PnL, gross exposure, positions).

**New tables** (§5): `orders`, `fills`, `positions` — added by migration
`alembic/versions/0002_paper_trading.py` (revision `0002`, down-revision `0001`).

---

## 4c. Agent runtimes (mock vs llm)

The analysis layer can run on either of two runtimes (`agent_service/service.py`),
and **neither can place an order**:

- **`mock`** — the deterministic, offline `MockAgent` (always available; no
  network). This is the default (`agent_runtime="mock"`).
- **`llm`** — the real, Anthropic-backed `LLMAgent` (`domain/agents/llm_agent.py`).
  It is used only when `agent_runtime="llm"` **and** an `ANTHROPIC_API_KEY` is
  present; on any LLM error, or a missing key, `AgentService.run` falls back to
  the mock so a well-formed result is always returned.

`LLMAgent` asks Claude (default model `claude-opus-4-8`) to produce exactly one
`AgentFinding` via a **forced tool call** — `tool_choice={"type":"tool",
"name":"emit_finding"}` guarantees structured output. Server-controlled fields
(agent name/version, timestamps, model, schema version, evidence `source_id`) are
filled in code, never by the model. The Anthropic client is **injected**, so the
agent is unit-testable offline; `build_async_anthropic_client` lazy-imports the
`anthropic` SDK only when a real client is constructed (the optional `[llm]`
extra). Settings: `agent_runtime` (`"mock"|"llm"`), `agent_model` (default
`claude-opus-4-8`), `agent_max_tokens` (default 2048).

`POST /api/v1/agents/run` runs the configured runtime (and persists the run);
`/system/status` reports the effective `agent_runtime`. See AGENT_DESIGN.md §6
for the runtime contract and the standing "no order authority" invariant.

---

## 4d. Research desk hierarchy (org chart)

The 21 analysis agents are organised as a research firm rather than a flat list
(`domain/agents/org.py`, ADR-016). Five **desks** — each with a designated
*lead* — feed a single **Chief** synthesizer, and work runs in **tiers**:
`VALIDATE → ANALYZE → SYNTHESIZE` (`Tier`). Data integrity validates first, the
four directional desks run in parallel, then the Chief synthesizes. Each desk
carries a directional **weight** the Chief uses when combining desk views into
the house prediction (the analysis desks' weights sum to ~1.0; the Chief is the
composer at weight 0).

| Desk (`Desk`) | Title (KO) | Tier | Weight | Lead | Members |
|---|---|---|---|---|---|
| `DATA_INTEGRITY` | 데이터·검증 데스크 | `VALIDATE` | 0.10 | Market Data Integrity Agent | 3 |
| `MACRO` | 거시·국제 데스크 | `ANALYZE` | 0.24 | Korea Macro Agent | 6 |
| `FLOW_TECH` | 수급·기술 데스크 | `ANALYZE` | 0.26 | Foreign and Institutional Flow Agent | 4 |
| `FUNDAMENTAL` | 실적·섹터 데스크 | `ANALYZE` | 0.24 | Earnings and Valuation Agent | 5 |
| `RISK` | 리스크·레드팀 데스크 | `ANALYZE` | 0.16 | Red-Team and Risk Agent | 2 |
| `CHIEF` | 수석 신디사이저 | `SYNTHESIZE` | 0.00 | Chief Market Synthesizer | 1 |

The roster is pure metadata over `catalog.py`: module-level assertions guarantee
every desk member matches a catalog agent name exactly and that the desks cover
**all 21 agents** (`3 + 6 + 4 + 5 + 2 + 1`). `org.py` runs nothing — the
orchestration lives in the prediction synthesizer (§4e). `GET /api/v1/agents/org`
exposes the chart read-only (`OrgResponse`: per-desk key/title/tier/weight/lead/
members, the three tier names, and the agent count). See AGENT_DESIGN.md §7.

---

## 4e. Prediction & daily brief

The product's primary output is a **house market prediction with a single-narrative
daily brief**. `PredictionService.generate` (`agent_service/prediction.py`) runs
**all** agents concurrently via the new `AgentService.run_all` (each agent still
falls back to mock on its own failure), flattens their findings, and hands them
to the **pure, deterministic** synthesizer (`domain/prediction/synthesizer.py`,
ADR-017):

```
all agents (run_all, concurrent) ──▶ findings
        │
        ▼
per-desk vote: Σ(impact × confidence × sign), lead-weighted (×1.5)  ──▶ DeskView per desk
        │
        ▼
Chief synthesis: overall_score = Σ(desk.weight × desk.score)
        │
        ├─▶ direction (BULLISH/BEARISH/NEUTRAL) + confidence
        ├─▶ regime  (classify_regime → one of 9 MarketRegime)
        ├─▶ instrument stances  (069500/122630/114800/252670 → long / inverse / 곱버스)
        ├─▶ 3 scenarios (probabilities sum to 1.0)
        └─▶ headline + single-narrative Korean brief
        │
        ▼
MarketPrediction  ──▶ persisted in market_predictions  ──▶ GET /prediction/latest, /brief
```

- **Desk views.** `_desk_view` scores each desk from its members' findings:
  `impact` weight (LOW 1 / MEDIUM 2 / HIGH 3) × `confidence` × direction sign,
  with the desk **lead** getting a ×1.5 bonus; the normalised signed score gives
  the desk's `lean` and `conviction`, plus its top drivers.
- **Chief synthesis.** The overall directional score is the **desk-weight-weighted**
  sum of desk scores; `direction` comes from a threshold band and `confidence`
  scales with `|score|` (capped 0.95).
- **Regime.** `classify_regime` (`domain/prediction/regime.py`) maps
  (direction, confidence, vol-high, risk-high, data-ok, top-desk) to one of the
  **9 `MarketRegime`** classes (e.g. bearish + high risk + high confidence →
  `CRISIS`; bullish + high confidence + calm → `RISK_ON_STRONG`; data not ok →
  `DATA_UNCERTAIN`).
- **Instrument stances (long / inverse / 곱버스).** Over the four-product ladder
  `069500` (LONG_1X), `122630` (LONG_2X), `114800` (INVERSE_1X), `252670`
  (INVERSE_2X "곱버스"), `stance_for` maps the house (direction, confidence,
  regime) to a `StanceLabel` (`OVERWEIGHT`/`NEUTRAL`/`UNDERWEIGHT`/`AVOID`) per
  instrument — so a **bearish** view yields an actionable *inverse / leveraged-
  inverse overweight*, not merely "avoid long". Leveraged (2x) products carry a
  Korean **leverage / daily-rebalancing volatility-decay** risk note and are
  pulled toward `NEUTRAL`/`AVOID` in choppy or crisis regimes.
- **Scenarios.** Three scenarios (base / reversal / sideways) whose
  probabilities are sized off `confidence` and **renormalised to sum to 1.0**.
- **Brief.** `_brief` composes one continuous Korean narrative (regime → house
  lean & confidence → lead desk's driver → Risk desk's caveat & invalidation →
  long/inverse/곱버스 positioning), not a bag of disjoint captions.

`MarketPrediction` (`domain/prediction/schemas.py`, `PREDICTION_SCHEMA_VERSION =
"1.0.0"`) carries `prediction_id`, `as_of`, `horizon` (default `D5`), `regime`,
`direction`, `confidence`, `data_quality`, `headline`, `brief`, `desk_views`,
`instrument_stances`, `scenarios`, `generated_by` (`"mock"|"llm"`), and
`agent_count`. `generated_by` is the runtime that actually produced the findings,
so the synthesis is honest about its inputs while remaining deterministic over
them.

**Endpoints** (`api/routes/prediction.py`, under `/api/v1`):

- `POST /prediction/run` — run all agents, synthesize, **persist**
  (`save_prediction`), audit-log (`AuditAction.AGENT_RUN`), return the
  `MarketPrediction`.
- `GET /prediction/latest` — the most recent stored prediction (404 until the
  first run).
- `GET /brief` — the latest daily brief as a `BriefResponse` (headline +
  narrative + the instrument stances with risk notes).
- `GET /agents/org` — the desk hierarchy (§4d).

**Worker.** The `refresh_prediction` job (every 30 min, `worker/scheduler.py`)
regenerates and persists a fresh prediction so `/prediction/latest` and `/brief`
stay current without a manual `POST`.

---

## 5. Persistence

The same ORM and the same single Alembic migration run on both backends; the
backend is chosen **solely by `DATABASE_URL`** (`config.py`):

- **SQLite (aiosqlite)** — local / CI default
  (`sqlite+aiosqlite:///./kospi_watcher.db`).
- **Postgres (asyncpg)** — prod (`postgresql+asyncpg://…`), via the optional
  `prod` extra (asyncpg is prod-only/optional, ADR-012).

Design constraints that make one migration cover both (ADR-008, ADR-009,
ADR-012):

- **Dialect-agnostic columns** — no JSONB, no native UUID. Lists/dicts use the
  generic SQLAlchemy `JSON` type; ids are `String`.
- **Decimal precision** — money/price are stored as **TEXT** via the
  `DecimalString` `TypeDecorator` (`db/types.py`), which serialises through
  `to_decimal`/`str` so SQLite's float-backed NUMERIC cannot silently round
  values.
- **Timestamps** are `DateTime(timezone=True)` (tz-aware, ADR-009).
- Alembic uses `render_as_batch=True` (`alembic/env.py`) so SQLite ALTERs work,
  and pulls the URL from `Settings`.

The ten tables (`db/models.py`); migration `alembic/versions/0001_initial.py`
creates the first six, `0002_paper_trading.py` adds `orders` / `fills` /
`positions`, and `0003_predictions.py` adds `market_predictions`:

| Table | Model | Notes |
|---|---|---|
| `instruments` | `Instrument` | symbol PK; seeded from `config/instruments.yml` (`db/seed.py`). |
| `agent_runs` | `AgentRunRow` | one row per agent invocation. |
| `agent_findings` | `AgentFindingRow` | FK → `agent_runs.id`; evidence/sectors/symbols as `JSON`. |
| `risk_decisions` | `RiskDecisionRow` | status, reason, `requires_human`, checks/failed_checks as `JSON`. |
| `order_proposals` | `OrderProposalRow` | unique `idempotency_key`; prices via `DecimalString`. |
| `orders` | `OrderRow` | a paper order + lifecycle (`status`); unique `idempotency_key`; FK target of `fills`; prices via `DecimalString` (migration `0002`). |
| `fills` | `FillRow` | one simulated fill; FK → `orders.id`; `price` via `DecimalString` (migration `0002`). |
| `positions` | `PositionRow` | **composite PK `(account, symbol)`**; signed `quantity`, `avg_cost`, `realized_pnl` via `DecimalString` (migration `0002`). |
| `market_predictions` | `PredictionRow` | one stored house prediction + daily brief; scalar columns (`as_of`/`direction`/`confidence`/`regime`/`headline`/`brief`/`generated_by`/`agent_count`) index the latest view, the full `MarketPrediction` lives in `payload` (`JSON`); `created_at` indexed for "latest" (migration `0003`). |
| `audit_logs` | `AuditLogRow` | **append-only** (ADR-006) — application code only inserts (`add_audit_log`); autoincrement integer id. |

On `api` startup the lifespan runs `Base.metadata.create_all` (dev convenience;
a no-op once Alembic has built the schema) and seeds instruments idempotently.

---

## 6. Cross-cutting concerns

- **Decimal-only money (ADR-008).** `domain/money.py` forbids `float` for any
  monetary/price value: `DecimalNoFloat` (a Pydantic `BeforeValidator`) and
  `to_decimal` both reject `float` at validation time. `DecimalString`
  (`db/types.py`) preserves precision at the storage layer.
- **Timezone-aware UTC + KST display (ADR-009).** `domain/time.py` stores UTC
  (`now_utc`, `to_utc`), displays Asia/Seoul (`to_kst`), and `ensure_aware`
  rejects naive datetimes. Pydantic `AwareDatetime` fields enforce this on
  agent/risk schemas; `system/status` returns both `server_time_utc` and
  `server_time_kst`.
- **Structured logging (logging_config.py / structlog).** JSON in prod, console
  renderer in dev. A `_redact_secrets` processor masks any key whose name looks
  like a credential (`secret`, `token`, `api_key`, `app_key`, `account_number`,
  `authorization`, …) with `***REDACTED***`, so secrets never reach the logs.
- **Deny-by-default risk (ADR-010).** Approval requires *all* implemented checks
  to pass; empty allow-lists deny everything; the engine is deterministic and
  LLM-free. `ApprovedOrder` is type-coupled to an `APPROVED` `RiskDecision`.
- **Secrets as `SecretStr`, never logged or returned.** All credentials in
  `Settings` (`anthropic_api_key`, `kis_*`, `kiwoom_*`, `dart_api_key`,
  `ecos_api_key`, `naver_*`) are `pydantic.SecretStr` and appear in no response
  schema (`api/schemas/responses.py`), so they cannot be serialised by accident.
- **Honest health reporting.** `infrastructure/redis_client.py` falls back to an
  in-memory `fakeredis` when `REDIS_URL` is unset or a real Redis is
  unreachable, and reports the backend truthfully (`backend="fakeredis"`).
  `/health` reports the DB backend (`sqlite`/`postgres`), the Redis backend and
  detail, and the trading-mode flags — and is `degraded` if the DB probe fails.

---

## 7. Tech stack & versions

Backend pins from `pyproject.toml` (`requires-python = ">=3.13"`; developed and
tested on Python 3.14 per ADR-012):

| Component | Pin |
|---|---|
| FastAPI | `fastapi>=0.115` |
| Uvicorn | `uvicorn>=0.34` |
| Pydantic v2 | `pydantic>=2.10` |
| pydantic-settings | `pydantic-settings>=2.7` |
| SQLAlchemy 2.0 | `sqlalchemy>=2.0.36` |
| aiosqlite | `aiosqlite>=0.20` |
| Alembic | `alembic>=1.14` |
| httpx | `httpx>=0.28` |
| APScheduler | `apscheduler>=3.11,<4` |
| redis | `redis>=5.2` |
| fakeredis | `fakeredis>=2.26` |
| structlog | `structlog>=24.4` |
| PyYAML | `pyyaml>=6.0` |
| tzdata | `tzdata>=2024.2` |
| asyncpg (prod extra) | `asyncpg>=0.30` |

Dev tooling: `pytest>=8.3`, `pytest-asyncio>=0.25`, `ruff>=0.8`, `mypy>=1.14`.
Ruff line length 100, target `py313`; mypy in strict-ish mode
(`disallow_untyped_defs`, pydantic plugin); pytest `asyncio_mode = "auto"`.

Front end (`apps/web/package.json`): **Next.js ^15.1.0**, **React ^19.0.0**,
TypeScript ^5.7, Tailwind ^3.4, `@tanstack/react-query` ^5.62, `zod` ^3.24,
Vitest ^2.1.

---

## 8. Deployment modes

### (a) Dockerless local mode (default)

Single venv with the package installed editable (`pip install -e .`), backed by
**SQLite (aiosqlite)** and the in-memory **fakeredis** fallback — no Docker,
Postgres, or Redis required (ADR-012). Services run with uvicorn / Python from
the repo root, e.g.:

```
.venv\Scripts\python -m uvicorn main:app --app-dir apps/api               --port 8000
.venv\Scripts\python -m uvicorn main:app --app-dir apps/agent-service     --port 8001
.venv\Scripts\python -m uvicorn main:app --app-dir apps/execution-gateway --port 8002
.venv\Scripts\python apps/worker/main.py
```

The web app runs via `npm run dev` (Next.js, port 3000).

### (b) docker-compose stack (PROD-shaped)

`docker-compose.yml` models the prod-shaped deployment: **Postgres 16** +
**Redis 7** + the **four Python services** (`api`, `agent-service`,
`execution-gateway`, `worker`) + the **web** app. The `api` service applies
`alembic upgrade head` before serving, and `DATABASE_URL` points at
`postgresql+asyncpg://…@postgres:5432/kospi_watcher`. The mandated safety env
defaults are kept (`TRADING_MODE=RESEARCH`, `LIVE_TRADING_ENABLED=false`,
`AUTO_EXECUTION_ENABLED=false`).

> **Not yet verified.** Per the file header and ADR-012, `docker compose up` has
> **not** been run in the development environment (no Docker daemon available).
> The compose file and Dockerfiles are provided for review and CI/CD and must be
> executed on a host with Docker before any operational use.
