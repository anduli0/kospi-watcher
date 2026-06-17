# KOSPI-WATCHER

Korean equity market (KOSPI / KOSPI200 / KOSDAQ) analysis and **risk-controlled** trading
research platform. A deterministic Risk Engine and an isolated Execution Gateway sit between
LLM analysis agents and any broker order path — **LLM agents can never place an order.**

> **Status:** Phase 0 + Phase 1 scaffold. `TRADING_MODE=RESEARCH`, live trading disabled.
> All market/financial data in this phase is **MOCK DATA — NOT REAL MARKET DATA.**

## Architecture at a glance

```
LLM agents (analysis only) ──▶ OrderProposal ──▶ deterministic Risk Engine ──▶ RiskDecision
                                                                                   │ APPROVED
                                                                                   ▼
                                                          Execution Gateway ──▶ BrokerAdapter (mock)
```

- **Agent Service** can create an `OrderProposal` but **cannot** import or call `submit_order`.
- **Only** the Execution Gateway may call broker order methods.
- **Only** the Risk Engine can create a `RiskDecision`; an `ApprovedOrder` cannot exist without one.

## Toolchain (this machine)

Windows 11 · Node v24 · Python 3.14 · npm workspaces (no pnpm) · single venv (src-layout
package `kospi_watcher`). Docker / PostgreSQL / Redis are **not installed locally** — the app
runs in a dockerless local mode (SQLite + fakeredis). See `docs/RUNBOOK.md`.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # core + editable pkg + dev tools
.venv\Scripts\python -m alembic upgrade head                   # SQLite by default
.venv\Scripts\python -m uvicorn main:app --app-dir apps/api    # API on :8000

cd apps/web && npm install && npm run dev                      # web on :3000
```

Full developer and operations guide: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).
Design docs and ADRs live under [`docs/`](docs/).
