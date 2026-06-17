"""Redis client with an honest in-memory fakeredis fallback.

Named ``redis_client`` to avoid shadowing the ``redis`` package. When
``REDIS_URL`` is unset or a real Redis is unreachable, we fall back to
``fakeredis`` and report the backend truthfully (``backend="fakeredis"``) so the
/health endpoint never claims a real cache that isn't there (see ADR-012).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RedisStatus:
    backend: str  # "redis" | "fakeredis"
    connected: bool
    detail: str


_client: Any | None = None
_status: RedisStatus | None = None


async def get_redis_client() -> Any:
    """Return a cached async Redis client, creating it (or a fakeredis fallback)
    on first use. The client API is compatible across both backends."""
    global _client, _status
    if _client is not None:
        return _client

    from kospi_watcher.config import get_settings

    settings = get_settings()

    if settings.redis_url:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await client.ping()
            _client = client
            _status = RedisStatus("redis", True, "connected to configured REDIS_URL")
            return _client
        except Exception as exc:
            _status = RedisStatus(
                "fakeredis",
                True,
                f"real Redis unavailable ({type(exc).__name__}); "
                "using in-memory fakeredis fallback",
            )
    else:
        _status = RedisStatus(
            "fakeredis", True, "REDIS_URL unset; using in-memory fakeredis fallback"
        )

    import fakeredis.aioredis

    _client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return _client


async def redis_status() -> RedisStatus:
    """Ensure the client is initialised and return its honest status."""
    if _status is None:
        await get_redis_client()
    assert _status is not None  # noqa: S101 - set by get_redis_client
    return _status


async def reset_redis() -> None:
    """Clear the cached client/status (used by tests)."""
    global _client, _status
    _client = None
    _status = None
