"""SyncManager — single-flight, cooldown, and honest failure reporting."""

from __future__ import annotations

import asyncio
from typing import Any

from kospi_watcher.briefing.sync import STAGES, SyncManager


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def _wait_done(manager: SyncManager) -> None:
    for _ in range(200):
        if not manager.running:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("sync did not finish")


async def test_single_flight_and_success_cycle() -> None:
    clock = FakeClock()
    gate: asyncio.Event = asyncio.Event()

    async def runner(set_stage: Any) -> dict[str, Any]:
        for stage in STAGES:
            set_stage(stage)
        await gate.wait()
        return {"direction": "BULLISH"}

    manager = SyncManager(cooldown_seconds=600, runner=runner, clock=clock)
    started, reason = manager.start()
    assert (started, reason) == (True, "started")
    assert manager.running

    # A second request while running is refused.
    started, reason = manager.start()
    assert (started, reason) == (False, "already_running")

    gate.set()
    await _wait_done(manager)
    status = manager.status()
    assert status["ok"] is True
    assert status["last_result"] == {"direction": "BULLISH"}
    assert status["stage"] is None


async def test_cooldown_blocks_then_expires() -> None:
    clock = FakeClock()

    async def runner(set_stage: Any) -> dict[str, Any]:
        return {}

    manager = SyncManager(cooldown_seconds=600, runner=runner, clock=clock)
    assert manager.start()[0]
    await _wait_done(manager)

    started, reason = manager.start()
    assert not started
    assert reason.startswith("cooldown:")

    clock.now += 601
    assert manager.cooldown_seconds_left() == 0
    assert manager.start()[0]
    await _wait_done(manager)


async def test_failure_reports_error_and_skips_cooldown() -> None:
    async def runner(set_stage: Any) -> dict[str, Any]:
        raise RuntimeError("news feed down")

    manager = SyncManager(cooldown_seconds=600, runner=runner)
    assert manager.start()[0]
    await _wait_done(manager)

    status = manager.status()
    assert status["ok"] is False
    assert "news feed down" in (status["error"] or "")
    # A failed run must not start a cooldown — allow an immediate retry.
    assert manager.cooldown_seconds_left() == 0
    assert manager.start()[0]
    await _wait_done(manager)
