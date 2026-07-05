"""Site-triggered full refresh: scrape → predict → news brief, with guards.

The public web can ask the server to refresh itself (``POST /api/v1/sync/run``).
Because that button is reachable from a public URL and a full refresh may run 21
subscription-backed LLM calls, the manager enforces:

- **Single-flight** — at most one refresh runs at a time; a second request is
  told one is already running.
- **Cooldown** — a successful refresh starts a cooldown window
  (``SYNC_COOLDOWN_MINUTES``); until it expires new requests are rejected with
  the remaining seconds, so a public button cannot burn the subscription.

The pipeline mirrors the 08:00 worker briefing (scrape → generate+save the
prediction → build+save the news daily brief) but does NOT push Telegram unless
``SYNC_NOTIFY_TELEGRAM`` is set — the worker cron owns delivery. Progress is
exposed per stage so the web can render it live.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from kospi_watcher.agent_service.prediction import PredictionService
from kospi_watcher.agent_service.service import AgentService
from kospi_watcher.config import get_settings
from kospi_watcher.db import repositories
from kospi_watcher.logging_config import get_logger

log = get_logger("sync")

STAGES = ("news", "prediction", "brief")
STAGE_KO = {"news": "뉴스 수집", "prediction": "예측 생성", "brief": "브리프 작성"}

_BRIEFING_UNIVERSE = ("069500", "114800", "252670")

# A runner receives a stage-reporting callback and returns a result summary.
SyncRunner = Callable[[Callable[[str], None]], Awaitable[dict[str, Any]]]


async def _default_runner(set_stage: Callable[[str], None]) -> dict[str, Any]:
    """The real pipeline (same steps as the 08:00 worker briefing)."""
    from kospi_watcher.briefing.service import (
        format_brief_message,
        format_report_message,
    )
    from kospi_watcher.infrastructure.db import get_sessionmaker
    from kospi_watcher.infrastructure.telegram import send_telegram_message
    from kospi_watcher.newsfeed.service import NewsService

    async with get_sessionmaker()() as session:
        set_stage("news")
        scrape = await NewsService().scrape(session)

        set_stage("prediction")
        headlines = await repositories.recent_headlines(session, limit=8)
        prediction = await PredictionService().generate(
            _BRIEFING_UNIVERSE, news_headlines=headlines
        )
        await repositories.save_prediction(session, prediction)
        await session.commit()

        set_stage("brief")
        brief = await NewsService().generate_daily_brief(session)

        if get_settings().sync_notify_telegram:
            await send_telegram_message(format_report_message(prediction))
            await send_telegram_message(format_brief_message(brief))

        return {
            "direction": prediction.direction.value,
            "confidence": prediction.confidence,
            "generated_by": prediction.generated_by,
            "news_added": scrape.added,
            "brief_items": brief.item_count,
        }


class SyncManager:
    """Process-wide state machine for site-triggered refreshes."""

    def __init__(
        self,
        *,
        cooldown_seconds: float,
        runner: SyncRunner | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cooldown = cooldown_seconds
        self._runner = runner or _default_runner
        self._clock = clock
        self._task: asyncio.Task[None] | None = None
        self._stage: str | None = None
        self._started_mono: float | None = None
        self._finished_mono: float | None = None
        self._started_at: str | None = None
        self._finished_at: str | None = None
        self._ok: bool | None = None
        self._error: str | None = None
        self._last_result: dict[str, Any] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def cooldown_seconds_left(self) -> int:
        """Seconds until a new refresh is allowed (0 = allowed now)."""
        if self.running:
            return 0
        anchor = self._finished_mono if self._ok else None
        if anchor is None:
            return 0
        left = self._cooldown - (self._clock() - anchor)
        return max(0, int(left))

    def start(self) -> tuple[bool, str]:
        """Begin a refresh in the background; returns (started, reason)."""
        if self.running:
            return False, "already_running"
        left = self.cooldown_seconds_left()
        if left > 0:
            return False, f"cooldown:{left}"
        self._stage = STAGES[0]
        self._started_mono = self._clock()
        self._finished_mono = None
        from kospi_watcher.domain.time import now_utc

        self._started_at = now_utc().isoformat()
        self._finished_at = None
        self._ok = None
        self._error = None
        self._task = asyncio.get_running_loop().create_task(self._run())
        return True, "started"

    async def _run(self) -> None:
        def set_stage(stage: str) -> None:
            self._stage = stage
            log.info("sync.stage", stage=stage)

        try:
            self._last_result = await self._runner(set_stage)
            self._ok = True
            log.info("sync.done", **(self._last_result or {}))
        except Exception as exc:  # a failed refresh must never crash the API
            self._ok = False
            self._error = f"{type(exc).__name__}: {exc}"
            log.warning("sync.failed", error=self._error)
        finally:
            from kospi_watcher.domain.time import now_utc

            self._stage = None
            self._finished_mono = self._clock()
            self._finished_at = now_utc().isoformat()

    def status(self) -> dict[str, Any]:
        runtime = AgentService().runtime_name
        return {
            "running": self.running,
            "stage": self._stage if self.running else None,
            "stage_ko": STAGE_KO.get(self._stage or "", "") if self.running else "",
            "stages": list(STAGES),
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "ok": self._ok,
            "error": self._error,
            "runtime": runtime,
            "cooldown_seconds": self.cooldown_seconds_left(),
            "last_result": self._last_result,
        }


_manager: SyncManager | None = None


def get_sync_manager() -> SyncManager:
    """Process-wide singleton (cooldown read from settings at first use)."""
    global _manager
    if _manager is None:
        _manager = SyncManager(
            cooldown_seconds=get_settings().sync_cooldown_minutes * 60.0
        )
    return _manager


def reset_sync_manager() -> None:
    """Drop the singleton (tests only — mirrors the reset_* provider helpers)."""
    global _manager
    _manager = None
