"""Generate the static data snapshot for the always-on cloud site (ADR-030).

Runs the FULL pipeline once in-process (scrape → predict → news brief), then
dumps every GET endpoint the web reads into ``apps/web/public/snapshot/*.json``.
The static Next.js build (``NEXT_PUBLIC_STATIC_SNAPSHOT=1``) serves those files
instead of a live API, so the site works on GitHub Pages with the PC off.

Design:
* Uses the real FastAPI app via an in-process ASGI transport (no network, no
  ports) — the snapshot is exactly what the live API would return.
* ``POST /api/v1/notify/morning`` runs the same scrape→predict→brief the 08:00
  worker cron runs, so the prediction reflects the configured runtime
  (``claude_cli`` on the subscription when the token is present, else the
  deterministic mock — the site is correct either way).
* Best-effort per endpoint: one failing endpoint never aborts the whole
  snapshot; the file is simply skipped and its page shows a soft error.

Run from the repo root:  python scripts/build_snapshot.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "apps" / "web" / "public" / "snapshot"

# The default market universe the home strip requests.
_QUOTE_SYMBOLS = "KOSPI,USDKRW,069500,114800,252670"

# (url, snapshot filename) — filenames MUST match lib/api.ts::snapshotUrl().
_GET_ENDPOINTS: list[tuple[str, str]] = [
    ("/health", "health"),
    ("/api/v1/system/status", "system-status"),
    ("/api/v1/agents", "agents"),
    ("/api/v1/agents/org", "agents-org"),
    (f"/api/v1/market/quotes?symbols={_QUOTE_SYMBOLS}", "market-quotes"),
    ("/api/v1/market/analysis", "market-analysis"),
    ("/api/v1/analysis/instruments", "analysis-instruments"),
    ("/api/v1/backtest", "backtest"),
    ("/api/v1/accuracy/track", "accuracy-track"),
    ("/api/v1/stocks/recommendations", "stocks-recommendations"),
    ("/api/v1/prediction/latest", "prediction-latest"),
    ("/api/v1/brief", "brief"),
    ("/api/v1/news?limit=60", "news-latest"),
    ("/api/v1/news/dates", "news-dates"),
    ("/api/v1/news/brief", "news-brief"),
    ("/api/v1/sync/status", "sync-status"),
]


def _write(name: str, payload: object) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


async def _main() -> int:
    # Deterministic, network-keyless-where-possible defaults for CI. Live data
    # (Yahoo quotes/history, Google News) stays on — it is keyless and real.
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./snapshot_build.db")
    os.environ.setdefault("REDIS_URL", "")
    os.environ.setdefault("MARKET_DATA_PROVIDER", "yahoo")
    os.environ.setdefault("NEWS_PROVIDER", "google")
    # Never send Telegram from the snapshot build (the worker owns delivery).
    os.environ["TELEGRAM_BOT_TOKEN"] = ""
    os.environ["TELEGRAM_CHAT_ID"] = ""
    # AGENT_RUNTIME is inherited from the workflow env (claude_cli when the
    # subscription token is present; otherwise the code falls back to mock).

    from httpx import ASGITransport, AsyncClient

    from kospi_watcher.api.app import create_app
    from kospi_watcher.db import models  # noqa: F401  (register tables)
    from kospi_watcher.db.seed import seed_instruments
    from kospi_watcher.infrastructure.db import (
        Base,
        get_engine,
        get_sessionmaker,
        reset_engine,
    )

    # Fresh schema (ASGITransport doesn't run lifespan; mirror the test setup).
    await reset_engine()
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with get_sessionmaker()() as session:
        await seed_instruments(session)
        await session.commit()

    app = create_app()
    transport = ASGITransport(app=app)
    ok = 0
    async with AsyncClient(transport=transport, base_url="http://snapshot") as client:
        # 1) Populate: run the real scrape → predict → news-brief pipeline.
        print("[snapshot] running pipeline (scrape → predict → brief)…", flush=True)
        try:
            r = await client.post("/api/v1/notify/morning", timeout=1800.0)
            r.raise_for_status()
            body = r.json()
            print(
                f"[snapshot] pipeline ok: dir={body.get('prediction_direction')} "
                f"news+{body.get('news_added')} brief={body.get('brief_items')}",
                flush=True,
            )
        except Exception as exc:
            print(f"[snapshot] WARN pipeline failed: {exc}", flush=True)

        # 2) Dump every GET endpoint.
        for url, name in _GET_ENDPOINTS:
            try:
                resp = await client.get(url, timeout=600.0)
                resp.raise_for_status()
                _write(name, resp.json())
                ok += 1
                print(f"[snapshot] {name}.json", flush=True)
            except Exception as exc:
                print(f"[snapshot] WARN {name}: {exc}", flush=True)

        # 3) Per-date news files (for the /news date picker).
        try:
            dates_resp = await client.get("/api/v1/news/dates", timeout=120.0)
            dates_resp.raise_for_status()
            dates = [d.get("date") for d in dates_resp.json().get("dates", [])]
            for d in dates:
                if not d:
                    continue
                nr = await client.get(f"/api/v1/news?date={d}&limit=60", timeout=120.0)
                if nr.status_code == 200:
                    _write(f"news-{d}", nr.json())
                    print(f"[snapshot] news-{d}.json", flush=True)
        except Exception as exc:
            print(f"[snapshot] WARN per-date news: {exc}", flush=True)

    print(f"[snapshot] done — {ok}/{len(_GET_ENDPOINTS)} core endpoints written.")
    # The site must have at least the forecast to be worth publishing.
    return 0 if (OUT_DIR / "prediction-latest.json").exists() else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
