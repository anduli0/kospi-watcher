"""Entry point for the `worker` service (APScheduler).

Run:
    .venv\\Scripts\\python apps/worker/main.py
"""

from __future__ import annotations

import asyncio
import socket

from kospi_watcher.config import get_settings
from kospi_watcher.logging_config import configure_logging, get_logger
from kospi_watcher.worker.scheduler import build_scheduler

# A bound socket acts as a cross-process single-instance lock: a second worker
# (e.g. from a duplicate logon trigger) fails to bind and exits, so only one
# scheduler ever runs — exactly one 08:00 briefing.
_LOCK_PORT = 18079


def _acquire_single_instance() -> socket.socket | None:
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", _LOCK_PORT))
        lock.listen(1)
    except OSError:
        lock.close()
        return None
    return lock


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
    _lock = _acquire_single_instance()
    if _lock is None:
        get_logger("worker").info("worker.already_running", port=_LOCK_PORT)
        raise SystemExit(0)
    asyncio.run(_main())
