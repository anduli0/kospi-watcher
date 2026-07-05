# ADR-028 — Subscription agent runtime (`claude_cli`) + site-triggered sync

Date: 2026-07-05 · Status: accepted

## Context

The `llm` runtime (ADR-015) bills the `ANTHROPIC_API_KEY`, whose credits ran
out; every cycle silently fell back to mock findings. The owner has a Claude
Max subscription usable headlessly through the local Claude Code CLI
(`claude -p`) with a long-lived token minted once by `claude setup-token`.
Separately, refreshing the site required either the 08:00 worker cron or a
local terminal — nothing a phone visitor could trigger.

## Decision

1. **`AGENT_RUNTIME=claude_cli`** — a third agent runtime.
   `infrastructure/claude_cli.py` exposes an AsyncAnthropic-*shaped* client
   whose `messages.create` runs one headless CLI call (`--tools ""`,
   `--no-session-persistence`, `--output-format json`, prompt via stdin,
   `--system-prompt` for the agent persona). The forced `emit_finding` tool
   call is emulated by asking for ONE JSON object matching the tool's input
   schema and wrapping the parsed object in a `tool_use`-shaped block, so
   `LLMAgent` (ADR-015) is reused unchanged. Auth comes from
   `CLAUDE_CODE_OAUTH_TOKEN` or `~/.claude/oauth-token.secret`; the subprocess
   env is scrubbed of inherited `CLAUDE_*`/`ANTHROPIC_*` vars. A per-client
   semaphore (default 3) bounds concurrent CLI processes; per-call timeout
   240s. Model default `claude-sonnet-5` (`AGENT_CLI_MODEL`).

2. **Site-triggered sync** — `POST /api/v1/sync/run` + `GET /api/v1/sync/status`
   (`briefing/sync.py`). Runs the same pipeline as the 08:00 briefing
   (scrape → predict+save → news brief) in the background with per-stage
   progress, but no Telegram unless `SYNC_NOTIFY_TELEGRAM=true`. Guards, since
   the button is on a public URL: **single-flight** (one run at a time) and a
   **success cooldown** (`SYNC_COOLDOWN_MINUTES`, default 10). The web's
   `SyncBanner` shows the engine (내 클로드로 분석 / 기본 분석 모드), last
   update time, live stage, and auto-triggers one refresh when the page is
   opened on data older than `SYNC_STALE_HOURS` (default 6) — so a phone visit
   refreshes the site by itself.

## Safety invariants kept

- Analysis-only: the CLI gets no tool surface; nothing new can place an order.
- Per-agent mock fallback unchanged — a cycle always completes, and
  `generated_by` / `model_name` / evidence `source_id` label the real source
  honestly (`claude_cli` / `claude-sonnet-5` / `LLM-claude-sonnet-5-…`).
- Mandated defaults untouched: `AGENT_RUNTIME` still defaults to `mock`;
  `claude_cli` is armed only via the local `.env`. `tests/conftest.py` pins
  `AGENT_RUNTIME=mock` so the suite can never spend subscription quota.
- The token is a secret: never logged, never in a response schema, read from
  the env/file at call time.

## Consequences

- The 21 agents produce real Claude findings on the subscription (≈3 min per
  cycle at concurrency 3) with zero API credits; the 08:00 worker cron and the
  daily-sync `prediction/run` POST automatically benefit.
- The public site is self-updating: stale visit → auto refresh; manual
  refresh button with visible progress; abuse bounded by cooldown+single-flight.
- If the token expires (valid ~1 year) or the CLI vanishes, everything
  degrades to the labelled mock path — same behavior as the dead-key era, but
  visible in `/sync/status` (`runtime: "mock"`).
