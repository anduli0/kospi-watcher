# CLAUDE.md — working agreement for KOSPI-WATCHER

Guidance for any AI agent (or human) working in this repository. Read this
before changing code. It encodes safety invariants that **must not** be relaxed.

## What this is

KOSPI-WATCHER is a Korean-equity (KOSPI) market-analysis and **risk-controlled**
trading-research platform. Its product now **centers on market prediction + a
single-narrative daily brief** (like the sibling Fed-Watcher / KRW-Watcher
systems); the trading path is **secondary and paper-only**. The 21 analysis
agents are organised as a **hierarchical research-desk org** — 5 desks
(`DATA_INTEGRITY`, `MACRO`, `FLOW_TECH`, `FUNDAMENTAL`, `RISK`) plus a `CHIEF`
synthesizer, across 3 tiers (`VALIDATE → ANALYZE → SYNTHESIZE`),
`domain/agents/org.py`, ADR-016. A **deterministic** synthesizer
(`domain/prediction/synthesizer.py`, ADR-017) aggregates one full agent sweep
(`AgentService.run_all`) into a `MarketPrediction`: market regime (one of 9),
direction/confidence, **long / inverse / leveraged-inverse (곱버스) instrument
stances** over `069500`/`122630`/`114800`/`252670`, three scenarios, and a Korean
brief — **identical over mock-or-LLM findings** (it is deterministic over the
findings; `generated_by` records only whether they came from `"mock"` or
`"llm"`). The prediction now also carries a **visible deliberation** — each
agent's position → the desk lead's consensus-vs-dissent reconciliation (an
`agreement` ratio) → the Chief's aligned-vs-conflicted cross-desk reconciliation
into the house view (`Deliberation`/`DeskDeliberation`/`ChiefDeliberation` in
`domain/prediction/schemas.py`, built in the **same deterministic pass**, ADR-019)
— and is explicitly **labelled** with its `subject` ("코스피200 지수 방향 …") and
`horizon_label`. The daily brief is **news-aware**: it weaves in recent scraped
headlines (`PredictionService.generate(news_headlines=…)`, populated from
`repositories.recent_headlines`) and lists them as `news_refs`, without changing
the deterministic math.

**News scraping (keyless, dated, retention).** A keyless **Google News RSS**
provider (`infrastructure/news/`, parsed with **`defusedxml`**, never raises,
mock fallback) feeds `NewsService.scrape` (`newsfeed/service.py`), which dedups,
upserts, and **prunes anything older than `news_retention_days` (default 14)**
into the dated `news_items` table (grouped by KST `date_kst`). It feeds the daily
brief; a worker `scrape_news` job (every 60 min) keeps it current (ADR-018).

New endpoints: `POST /api/v1/prediction/run`, `GET /api/v1/prediction/latest`,
`GET /api/v1/brief`, `GET /api/v1/agents/org`, `GET /api/v1/news`,
`GET /api/v1/news/dates`, `POST /api/v1/news/scrape`; predictions persist in
`market_predictions` and a worker `refresh_prediction` job (every 30 min) keeps
the latest (news-aware) brief current. Predictions/stances are **display-only** —
they are NOT order authority (the inverse/곱버스 ETFs are `tradable=false`, and any
order still passes the deny-by-default Risk Engine).

The web is a **modern multi-page UI** (Pretendard font, dark fintech palette,
Korea up=red/down=blue) with an 오늘 / 예측 / 뉴스 / 에이전트 / 트레이딩 / 시스템
nav and a **disclaimer + ownership footer** (`© 2026 YellowScale · 안민규`);
`/prediction` renders the deliberation thread + Chief reconciliation, `/news` the
dated headlines (ADR-019).

It has two halves with a hard wall between them:

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
  domain/                 # pure, no I/O: enums, time, money, agents, prediction, risk, execution
                          #   agents/llm_agent.py = real Anthropic agent (ADR-015)
                          #   agents/org.py = research-desk org chart (ADR-016)
                          #   prediction/ = synthesizer + regime + long/inverse ladder (ADR-017)
                          #   execution/{paper,position}.py = PAPER fills + PnL (ADR-014)
  infrastructure/         # db engine/session, redis client (fakeredis fallback)
                          #   marketdata/ = keyless Yahoo + mock provider (ADR-013)
                          #   news/ = keyless Google News RSS + mock provider (ADR-018)
  db/                     # ORM models (11 tables), repositories, custom types, seed
  api/                    # FastAPI app, routes, request/response schemas
  agent_service/          # isolated analysis service (mock + llm) + PredictionService
  execution_gateway/      # isolated execution boundary (app + gateway)
  trading/                # TradingService — the PAPER execution orchestrator
  newsfeed/               # NewsService — scrape → dedup-upsert → retention prune (ADR-018)
  worker/                 # APScheduler jobs (heartbeat, mock_agent_sweep,
                          #   scrape_news, refresh_prediction)
apps/                     # per-service entry points (api, agent-service,
                          # execution-gateway, worker) + web (Next.js, modern multi-page UI)
alembic/                  # four migrations (0001 initial, 0002 paper trading,
                          #   0003 market_predictions, 0004 news), SQLite + Postgres compatible
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
# Prediction + daily brief (the primary product surface) — no opt-in needed:
# POST /api/v1/prediction/run  → run all agents, synthesize, persist, return MarketPrediction
#                                (now incl. a visible deliberation + subject/horizon labels + news_refs).
# GET  /api/v1/prediction/latest  → latest stored prediction (404 until first run).
# GET  /api/v1/brief              → latest daily brief (headline + narrative + long/inverse/곱버스 stances).
# GET  /api/v1/agents/org         → the 5-desk + Chief research hierarchy (read-only).
# The worker's refresh_prediction job (every 30 min) keeps latest/brief current.

# News scraping (keyless Google News RSS) feeds the daily brief — no opt-in needed:
# POST /api/v1/news/scrape  → fetch configured topics, dedup-upsert, prune past retention.
# GET  /api/v1/news[?date=YYYY-MM-DD]  → dated headlines;  GET /api/v1/news/dates → dates + counts.
# The worker's scrape_news job (every 60 min) keeps it current. Force offline mock if needed:
$env:NEWS_PROVIDER = "mock"   # default "google" (keyless); NEWS_RETENTION_DAYS defaults to 14.

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
  paper execution §4b, agent runtimes §4c, the research-desk org §4d, the
  prediction / daily-brief engine §4e, news scraping & retention §4f, the agent
  deliberation §4g, and the multi-page web UI §6a).
- `docs/DATA_DICTIONARY.md` — every table, enum, schema field, and key settings.
- `docs/AGENT_DESIGN.md` — the 21 agents, the finding contract, the runtimes, the
  desk org + prediction synthesis (§7), the deliberation & reconciliation (§7.5),
  and the news-aware brief (§7.6).
- `docs/PRODUCT_SPEC.md` — product goals; §12 covers the prediction engine +
  daily brief + the long/short (인버스/곱버스) ladder; §13 covers news scraping +
  the visible agent deliberation + the UI/disclaimer.
- `docs/TRADING_SAFETY.md` — the risk checks, kill-switch model, and the
  PAPER-implemented / LIVE-not-implemented boundary (§12).
- `docs/adr/` — the 19 architecture decision records (ADR-013/014/015 cover the
  market-data, paper-execution, and LLM-runtime decisions; ADR-016/017 cover the
  research-desk org and the deterministic prediction / daily-brief engine;
  ADR-018/019 cover keyless news scraping + the visible deliberation and modern
  multi-page UI).
