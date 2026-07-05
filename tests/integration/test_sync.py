"""Site-triggered sync routes — status, run, single-flight/cooldown guards.

Runs entirely offline: mock news + market providers, mock agent runtime. The
POST actually executes the full scrape → predict → brief pipeline in the
background, so the test polls the status route until it completes.
"""

from __future__ import annotations

import asyncio

from httpx import AsyncClient

from kospi_watcher.briefing.sync import reset_sync_manager


async def _wait_finished(client: AsyncClient, attempts: int = 300) -> dict:
    for _ in range(attempts):
        status = (await client.get("/api/v1/sync/status")).json()
        if not status["running"] and status["ok"] is not None:
            return status
        await asyncio.sleep(0.05)
    raise AssertionError("sync did not finish in time")


async def test_sync_status_fresh_db(client: AsyncClient) -> None:
    reset_sync_manager()
    resp = await client.get("/api/v1/sync/status")
    assert resp.status_code == 200
    status = resp.json()
    assert status["running"] is False
    assert status["runtime"] == "mock"  # pinned by conftest
    assert status["last_prediction_at"] is None
    assert status["stale"] is True  # nothing generated yet
    assert status["cooldown_seconds"] == 0


async def test_sync_run_full_pipeline_and_guards(client: AsyncClient) -> None:
    reset_sync_manager()
    resp = await client.post("/api/v1/sync/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["started"] is True
    assert body["reason"] == "started"

    # While running (or already done), a repeat request never double-runs.
    repeat = (await client.post("/api/v1/sync/run")).json()
    assert repeat["started"] is False
    assert repeat["reason"] == "already_running" or repeat["reason"].startswith("cooldown:")

    status = await _wait_finished(client)
    assert status["ok"] is True
    assert status["error"] is None
    assert status["last_result"]["direction"] in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert status["last_result"]["generated_by"] == "mock"
    assert status["last_prediction_at"] is not None
    assert status["stale"] is False

    # Success starts the cooldown window.
    after = (await client.post("/api/v1/sync/run")).json()
    assert after["started"] is False
    assert after["reason"].startswith("cooldown:")
    assert after["status"]["cooldown_seconds"] > 0

    reset_sync_manager()
