"""Entry point for the `worker` service (APScheduler).

Run:
    .venv\\Scripts\\python apps/worker/main.py
"""

from __future__ import annotations

import asyncio

from kospi_watcher.config import get_settings
from kospi_watcher.logging_config import configure_logging, get_logger
from kospi_watcher.worker.scheduler import build_scheduler


async def _main() -> None:
    settings = get_settings()
    configure_logging(json_logs=settings.log_json, level=settings.log_level)
    log = get_logger("worker")
    scheduler = build_scheduler()
    scheduler.start()
    log.info("worker.started", jobs=[j.id for j in scheduler.get_jobs()])
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(_main())
