"""KRX (Korea Exchange) trading-day calendar — Asia/Seoul.

The daily brief and the prediction report are generated **every calendar day**,
but the market only trades on business days. On a closed day the prose must NOT
speak as if a session happened ("오늘 증시는 강세") — it frames the house view as
the *next trading session*'s outlook instead. This module answers the one
question that distinction needs: "is this KST date a trading day?".

Closed = Saturday/Sunday **or** a KRX holiday. Holidays are a hand-maintained,
data-driven table per year (KRX publishes the schedule annually; substitute
holidays 대체공휴일 and the year-end closing day 연말 휴장 are included). Weekends
are always handled deterministically, so a year whose holidays aren't loaded yet
still degrades to a correct-on-weekdays answer — call :func:`holidays_loaded` to
know whether holiday coverage exists for a given year.

Pure data + arithmetic: no I/O, safe to import from ``domain``.
"""

from __future__ import annotations

from datetime import date

# KRX market holidays by KST calendar date. Includes 대체공휴일 (substitute
# holidays) and the year-end 연말 휴장 (the last business day of the year is a
# non-trading settlement holiday). Weekend dates are listed too for documentation
# even though the weekday check already covers them.
#
# ⚠️ Verify and extend this table every December when KRX publishes the next
# year's 휴장일 일정. Sources: 한국거래소(KRX) 연간 휴장일 공지.
_KRX_HOLIDAYS: dict[int, frozenset[str]] = {
    2025: frozenset(
        {
            "2025-12-25",  # 성탄절
            "2025-12-31",  # 연말 휴장 (최종 매매일 12-30)
        }
    ),
    2026: frozenset(
        {
            "2026-01-01",  # 신정
            "2026-02-16",  # 설날 연휴
            "2026-02-17",  # 설날
            "2026-02-18",  # 설날 연휴
            "2026-03-02",  # 삼일절 대체공휴일 (3-1 일요일)
            "2026-05-01",  # 근로자의 날
            "2026-05-05",  # 어린이날
            "2026-05-25",  # 부처님오신날 대체공휴일 (5-24 일요일)
            "2026-06-06",  # 현충일 (토요일)
            "2026-08-17",  # 광복절 대체공휴일 (8-15 토요일)
            "2026-09-24",  # 추석 연휴
            "2026-09-25",  # 추석
            "2026-09-26",  # 추석 연휴 (토요일)
            "2026-10-05",  # 개천절 대체공휴일 (10-3 토요일)
            "2026-10-09",  # 한글날
            "2026-12-25",  # 성탄절
            "2026-12-31",  # 연말 휴장 (최종 매매일 12-30)
        }
    ),
}


def holidays_loaded(year: int) -> bool:
    """True iff the KRX holiday table covers ``year``.

    When False, :func:`is_trading_day` still answers correctly for weekends but
    treats every weekday as a trading day (the honest fallback until that year's
    schedule is added to ``_KRX_HOLIDAYS``).
    """
    return year in _KRX_HOLIDAYS


def is_market_holiday(d: date) -> bool:
    """True iff ``d`` (a KST calendar date) is a KRX holiday — weekends excluded."""
    return d.isoformat() in _KRX_HOLIDAYS.get(d.year, frozenset())


def is_trading_day(d: date) -> bool:
    """True iff KRX trades on ``d`` — a KST weekday that is not a holiday."""
    return d.weekday() < 5 and not is_market_holiday(d)


def closed_reason(d: date) -> str | None:
    """Korean reason the market is closed on ``d``, or ``None`` if it trades."""
    if d.weekday() >= 5:
        return "주말"
    if is_market_holiday(d):
        return "휴장일"
    return None


def is_trading_day_kst(date_kst: str) -> bool:
    """Convenience over :func:`is_trading_day` for an ISO ``YYYY-MM-DD`` KST string.

    On an unparseable string it returns ``True`` (fail open — never let a bad date
    string suppress the brief), which the callers also treat as "assume open".
    """
    try:
        return is_trading_day(date.fromisoformat(date_kst))
    except ValueError:
        return True
