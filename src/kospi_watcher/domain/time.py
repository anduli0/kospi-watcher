"""Timezone-aware datetime helpers (see ADR-009).

Invariants:
- Every datetime crossing a domain boundary MUST be timezone-aware.
- Internal storage is UTC.
- User-facing display is Asia/Seoul (KST).
- Time-sensitive records carry the four point-in-time concepts explicitly:
  ``event_time``, ``published_at``, ``available_at``, ``ingested_at``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

UTC = UTC
KST = ZoneInfo("Asia/Seoul")


def now_utc() -> datetime:
    """Current instant as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def is_aware(dt: datetime) -> bool:
    """True iff ``dt`` carries a concrete UTC offset."""
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def ensure_aware(dt: datetime) -> datetime:
    """Return ``dt`` unchanged if aware, else raise.

    Naive datetimes are forbidden everywhere in the domain so that
    point-in-time logic and UTC storage are unambiguous.
    """
    if not is_aware(dt):
        raise ValueError(
            "naive datetime is not allowed; all domain datetimes must be timezone-aware"
        )
    return dt


def to_utc(dt: datetime) -> datetime:
    """Convert an aware datetime to UTC (raises on naive input)."""
    return ensure_aware(dt).astimezone(UTC)


def to_kst(dt: datetime) -> datetime:
    """Convert an aware datetime to Asia/Seoul for display (raises on naive)."""
    return ensure_aware(dt).astimezone(KST)


def isoformat_utc(dt: datetime) -> str:
    """ISO-8601 string in UTC."""
    return to_utc(dt).isoformat()
