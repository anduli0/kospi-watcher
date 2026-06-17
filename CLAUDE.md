# CLAUDE.md — working agreement for KOSPI-WATCHER

Guidance for any AI agent (or human) working in this repository. Read this
before changing code. It encodes safety invariants that **must not** be relaxed.

## What this is

KOSPI-WATCHER is a Korean-equity (KOSPI) market-analysis and **risk-controlled**
trading-research platform. It has two halves with a hard wall between them:

1. **Analysis** — 21 agents that *only* analyze. They emit `AgentFinding`s and
   have **no order-execution surface** (`AnalysisAgent` protocol in
   `src/kospi_watcher/domain/agents/base.py`). Agents can run on the deterministic
   **mock** runtime (default) or a **real Anthropic LLM** (`AGENT_RUNTIME=llm` +
   `ANTHROPIC_API_KEY`, default model `claude-opus-4-8`, mock fallback on any
   error) — **neither runtime has order authority** (ADR-015).
2. **Execution** — a deterministic, **deny-by-default** Risk Engine is the *only*
   gate to an order, and `ExecutionGateway` is the *only* code that ever calls a
   broker. **PAPER (simulated) execution IS implemented and safe**: it moves no
   real money and contacts no real broker, runs only when `TRADING_MODE=PAPER`,
   and still passes the full Risk Engine + state machine + audit path
   (`PAPER_EXECUTION_IMPLEMENTED = True`; `PaperBrokerAdapter` / `TradingService`,
   ADR-014). **Live execution remains NOT implemented in this phase**
   (`LIVE_EXECUTION_IMPLEMENTED = False` in `src/kospi_watcher/config.py`); the
   gateway allows only the simulated MOCK/PAPER brokers and blocks any live broker.

Market prices (KOSPI/USDKRW/KOSPI200 ETFs) are **live via keyless Yahoo Finance**
with a labelled mock fallback; the provider never raises (ADR-013).

If you ever find yourself making an LLM/agent able to place an order, making a
single env var enough to send a *live* order, or letting PAPER fills look like
real ones, stop — that violates the design.

## Non-negotiable safety invariants

- **Deny-by-default risk.** Empty allow-lists mean *deny everything*. Every order
  must pass `RiskEngine.evaluate(...)`; only an `APPROVED` `RiskDecision` can
  build an `ApprovedOrder` (via `ApprovedOrder.from_decision`). See ADR-010.
- **No `float` for money or price — ever.** Use `Decimal`. Pydantic price fields
  use `DecimalNoFloat`, which raises on a raw `float`; the DB stores `Decimal` as
  TEXT (`DecimalString`) so precision is never lost. See ADR-008.
- **Time is timezone-aware and stored in UTC**; display is KST (Asia/Seoul).
  Naive datetimes are rejected at domain boundaries (`domain/time.py`). See ADR-009.
- **Arming live execution requires multiple independent gates** (mode +
  `live_trading_enabled` [+ `auto_execution_enabled` for unattended]). A single
  flag is never sufficient (`Settings.live_execution_armed` / `auto_execution_armed`).
  Even fully armed, **no live order can be produced** — the live path is not
  implemented (`LIVE_EXECUTION_IMPLEMENTED = False`).
- **PAPER is the only implemented execution mode, and it is simulated.** Orders
  execute only under `TRADING_MODE=PAPER`; `RESEARCH` refuses execution (HTTP 409).
  Paper fills are produced by `PaperBrokerAdapter.simulate_fill` — **no real
  broker, no real money** — and are labelled (`liquidity="PAPER"`,
  `PAPER-…` ids). Never present a simulated fill as a real one. See ADR-014.
- **Mandated defaults**: `TRADING_MODE=RESEARCH`, `LIVE_TRADING_ENABLED=false`,
  `AUTO_EXECUTION_ENABLED=false`. Do not change these defaults. (PAPER is opt-in
  per run/session via `TRADING_MODE=PAPER`.)
- **Secrets** are `SecretStr` and never logged or returned in any response schema.
- **`config/risk_limits.yml` is safety-relevant.** Any change to allow-lists or
  limits must be recorded (ADR or change log) and reviewed.
- **`audit_logs` is append-only** (ADR-006). No update/delete path in app code.
- **Mock data is always labelled; live data is sourced honestly.** The mock agent
  runtime and the simulated brokers tag output (`[MOCK]`, `source="mock"`,
  `PAPER BROKER — SIMULATED FILLS…`) so it can never be mistaken for a real order.
  Live quotes carry `source="yahoo"`; fallback/offline quotes are `source="mock"`,
  `stale=True`. Don't blur the two.

## Layout

```
src/kospi_watcher/        # the package (src-layout, ADR-011)
  domain/                 # pure, no I/O: enums, time, money, agents, risk, execution
                          #   agents/llm_agent.py = real Anthropic agent (ADR-015)
                          #   execution/{paper,position}.py = PAPER fills + PnL (ADR-014)
  infrastructure/         # db engine/session, redis client (fakeredis fallback)
                          #   marketdata/ = keyless Yahoo + mock provider (ADR-013)
  db/                     # ORM models (9 tables), repositories, custom types, seed
  api/                    # FastAPI app, routes, request/response schemas
  agent_service/          # isolated analysis service (mock + llm runtimes)
  execution_gateway/      # isolated execution boundary (app + gateway)
  trading/                # TradingService — the PAPER execution orchestrator
  worker/                 # APScheduler jobs
apps/                     # per-service entry points (api, agent-service,
                          # execution-gateway, worker) + web (Next.js)
alembic/                  # two migrations (0001 initial, 0002 paper trading),
                          #   SQLite + Postgres compatible
config/                   # risk_limits.yml, instruments.yml (+ agents/strategies)
docs/                     # ARCHITECTURE, DATA_DICTIONARY, AGENT_DESIGN, PRODUCT_SPEC,
                          # TRADING_SAFETY, THREAT_MODEL, RUNBOOK, ULTRAPLAN, adr/
tests/                    # unit + integration (pytest, httpx ASGI)
```

The dependency rule: **everything points inward at `domain`**; `domain` imports
nothing app-specific (no FastAPI, no SQLAlchemy session, no I/O).

## Local development (dockerless mode)

Windows PowerShell paths shown; the project targets Python **>=3.13** and is
developed/tested on 3.14.

```powershell
# 1. venv + install (SQLite + fakeredis; no Docker needed)
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

# 2. migrate the local SQLite DB
.venv\Scripts\python -m alembic upgrade head

# 3. run the API (http://localhost:8000, docs at /docs)
.venv\Scripts\python -m uvicorn main:app --app-dir apps/api --port 8000

# 4. the worker (optional)
.venv\Scripts\python apps/worker/main.py

# 5. the web app
cd apps/web; npm install; npm run dev   # http://localhost:3000
```

`DATABASE_URL` selects the backend: SQLite (`sqlite+aiosqlite://...`, default) for
local/CI, Postgres (`postgresql+asyncpg://...`) for prod. `REDIS_URL` empty →
in-memory fakeredis (reported honestly at `/health`). Copy `.env.example` →
`.env` to override; never commit `.env`.

### Enabling the new capabilities

```powershell
# Live market data is ON by default (keyless Yahoo). Force offline mock if needed:
$env:MARKET_DATA_PROVIDER = "mock"
# GET /api/v1/market/quotes  → live (or mock) quotes for KOSPI/USDKRW/ETFs.

# PAPER (simulated) execution — opt in per session; live stays gated/unimplemented:
$env:TRADING_MODE = "PAPER"           # RESEARCH (default) refuses execution (HTTP 409)
# POST /api/v1/orders  → risk-gated simulated fill; GET /api/v1/positions, /api/v1/account.

# Real LLM agents (Anthropic). Needs the [llm] extra + a key; falls back to mock:
.venv\Scripts\python -m pip install -e ".[llm]"
$env:AGENT_RUNTIME = "llm"; $env:ANTHROPIC_API_KEY = "sk-ant-..."
# AGENT_MODEL defaults to claude-opus-4-8; set claude-sonnet-4-6 for a cheaper tier.
# POST /api/v1/agents/run  → configured runtime; /system/status reports agent_runtime.
```

Do **not** persist `TRADING_MODE`/`AGENT_RUNTIME` overrides into committed defaults
or `.env.example` — the mandated defaults (RESEARCH / mock-capable) stay put.

## Quality gates — run before declaring anything done

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m alembic upgrade head   # then `downgrade base` to verify reversibility
cd apps/web; npm run lint; npm run typecheck; npm run build
```

`docker compose up` is **not yet verified** in this environment (no Docker
daemon). Treat `docker-compose.yml` and the Dockerfiles as drafts for review/CI
until run on a host with Docker.

## Conventions

- Pydantic v2 everywhere; `model_config = ConfigDict(extra="forbid")` on domain
  models. Enums are `StrEnum` — persist the string *value*, never the position.
- Module names avoid shadowing stdlib/3rd-party (`logging_config.py`,
  `infrastructure/redis_client.py`).
- Tests: `pytest` with `asyncio_mode=auto`; integration tests use an httpx
  `ASGITransport` against a throwaway SQLite DB (see `tests/conftest.py`).
- New LLM-backed agents should target the latest Claude models (the `LLMAgent`
  default is `claude-opus-4-8`), use the forced `emit_finding` tool for structured
  output, let the server fill trusted fields, keep the `AgentFinding` schema (bump
  `AGENT_FINDING_SCHEMA_VERSION` on breaking changes), and must remain
  analysis-only (no order authority). See ADR-015 / AGENT_DESIGN §6.

## Where to read more

- `docs/ARCHITECTURE.md` — components, layering, data flow (incl. market data §4a,
  paper execution §4b, agent runtimes §4c).
- `docs/DATA_DICTIONARY.md` — every table, enum, schema field, and key settings.
- `docs/AGENT_DESIGN.md` — the 21 agents, the finding contract, and the runtimes.
- `docs/TRADING_SAFETY.md` — the risk checks, kill-switch model, and the
  PAPER-implemented / LIVE-not-implemented boundary (§12).
- `docs/adr/` — the 15 architecture decision records (ADR-013/014/015 cover the
  new market-data, paper-execution, and LLM-runtime decisions).
