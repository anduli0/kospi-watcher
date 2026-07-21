# ADR-030 — Always-on cloud site (GitHub Actions + Pages), PC-independent

Date: 2026-07-06 · Status: accepted

## Context

The public site was served from the home PC: Tailscale Funnel maps
`krw-watcher.tail3e31a9.ts.net:8443` → `localhost:3100` (the Next.js prod
server) → `localhost:18080` (FastAPI). This makes the PC a hard dependency —
when it is off (or asleep, or tailscaled is down), the site is completely
unreachable from mobile. The requirement is a site that works on a phone
**regardless of the PC's state**.

Two facts make a clean solution possible:
1. The sibling **gucci-intel** already runs cloud-first on GitHub Actions +
   GitHub Pages, including running `claude -p` in the cloud via a
   `CLAUDE_CODE_OAUTH_TOKEN` repo secret. So the Claude subscription *can* run
   PC-independently on GitHub's runners.
2. KOSPI's forecast is **100% deterministic** (the synthesizer over
   `trend_core` + BOK + calibration; ADR-017/025/029). The LLM agents only add
   deliberation colour. So a cloud run produces the same core prediction with or
   without the subscription.

## Decision

Add a second, always-on deployment that runs entirely on GitHub infrastructure,
alongside (not replacing) the live PC deployment.

**Static-snapshot web build.** A build-time flag `NEXT_PUBLIC_STATIC_SNAPSHOT=1`
switches the Next.js app into a backend-less mode:
- `lib/api.ts` serves every GET from a pre-generated `<basePath>/snapshot/*.json`
  file (mapped by `snapshotUrl()`), and rejects mutations.
- `next.config.mjs` emits a static export (`output: "export"`) under a project
  `basePath` (`/kospi-watcher`), `images.unoptimized`, `trailingSlash`.
- `SyncBanner` and the home CTA render read-only cloud variants (no live
  trigger; they show "클라우드에서 매일 자동 업데이트").
The live PC build leaves the flag unset and keeps the same-origin API proxy, so
**the existing deployment is completely unchanged** — both modes coexist in one
codebase.

**Snapshot generator.** `scripts/build_snapshot.py` runs the real pipeline once
in-process over an ASGI transport (scrape → predict → news brief via
`POST /notify/morning`), then dumps every GET endpoint the web reads into
`apps/web/public/snapshot/`. The snapshot is byte-for-byte what the live API
would return.

**Workflow.** `.github/workflows/cloud-site.yml` (cron + `workflow_dispatch`):
- 07:20 KST → `AGENT_RUNTIME=claude_cli`: the daily analysis, 21 agents on the
  subscription via `claude -p` (token from the `CLAUDE_CODE_OAUTH_TOKEN` secret).
- 09:00–15:30 KST weekdays, every 30 min (+ 15:40 close print) →
  `AGENT_RUNTIME=mock`: market-hours refresh so prices/prediction stay near-live
  while KRX trades. Free (public-repo Actions minutes), no subscription spend;
  GitHub cron can lag a few minutes, so effective staleness is ~30–40 min worst
  case. The runtime gate is `hour < 8` (07:20 slot only) so these never trigger
  the full Claude analysis.
- 13:00 KST weekends / 20:00 KST daily → `AGENT_RUNTIME=mock`: off-hours refresh.
- `workflow_dispatch` → full Claude analysis.
Each run builds the snapshot, static-exports the web, and deploys to Pages via
`actions/deploy-pages`.

**Public URL:** `https://anduli0.github.io/kospi-watcher/` — always on, mobile,
PC-independent, $0. Repo `anduli0/kospi-watcher` is public (matching
gucci-intel-engine; no secrets are committed — `.env` is gitignored and the
token lives only as an encrypted Actions secret).

## Consequences

- The site is reachable 24/7 from any phone even with the PC off; a daily Claude
  analysis and two deterministic refreshes keep it current.
- The PC deployment (Tailscale `:8443`, live "지금 업데이트" button, worker
  Telegram) remains as an optional **live/on-demand mirror** — nothing about it
  changed.
- Robustness: if the subscription token ever fails in the cloud, the pipeline
  falls back to the deterministic mock runtime (per-agent), so the site still
  publishes a correct forecast — it just loses the LLM deliberation colour.
- Trade-off: the cloud site is a **snapshot** — no live "refresh now" (mutations
  are disabled) and quotes are as fresh as the last cron run, not real-time.
  That matches the product (a daily forecast + brief), and the snapshot
  timestamp is shown in the banner. Real-time interaction remains on the live
  PC URL when the PC is on.
- Branch/Pages setup gotchas recorded for future repos: GitHub Actions does not
  index workflows when the default branch name contains a slash (use `main`),
  and the auto-created `github-pages` environment restricts deploys to the
  branch that was default when Pages was enabled (clear its
  `deployment_branch_policy`).
