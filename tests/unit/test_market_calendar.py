"""KRX trading-day calendar — weekends + holidays (Asia/Seoul)."""

from __future__ import annotations

from datetime import date

from kospi_watcher.domain.market_calendar import (
    closed_reason,
    holidays_loaded,
    is_market_holiday,
    is_trading_day,
    is_trading_day_kst,
)


def test_weekend_is_not_a_trading_day() -> None:
    # 2026-06-20 is a Saturday, 2026-06-21 a Sunday.
    assert is_trading_day(date(2026, 6, 20)) is False
    assert is_trading_day(date(2026, 6, 21)) is False
    assert closed_reason(date(2026, 6, 20)) == "주말"
    assert is_market_holiday(date(2026, 6, 20)) is False  # weekend, not a holiday


def test_ordinary_weekday_is_a_trading_day() -> None:
    # 2026-06-19 is a Friday with no holiday.
    assert is_trading_day(date(2026, 6, 19)) is True
    assert closed_reason(date(2026, 6, 19)) is None


def test_krx_holiday_on_a_weekday_is_closed() -> None:
    # New Year's Day 2026 is a Thursday.
    assert is_market_holiday(date(2026, 1, 1)) is True
    assert is_trading_day(date(2026, 1, 1)) is False
    assert closed_reason(date(2026, 1, 1)) == "휴장일"


def test_year_end_closing_day_is_closed() -> None:
    # KRX-specific: the last business day (2026-12-31, Thu) is a 연말 휴장.
    assert is_trading_day(date(2026, 12, 31)) is False


def test_substitute_holiday_is_closed() -> None:
    # 삼일절 falls on Sunday 2026-03-01 → substitute holiday Monday 2026-03-02.
    assert is_trading_day(date(2026, 3, 2)) is False


def test_string_helper_and_fallback() -> None:
    assert is_trading_day_kst("2026-06-19") is True
    assert is_trading_day_kst("2026-06-20") is False
    # Unparseable string fails open (assume the market is open).
    assert is_trading_day_kst("not-a-date") is True


def test_holidays_loaded_reports_coverage() -> None:
    assert holidays_loaded(2026) is True
    # An unloaded future year degrades to weekday-only (still correct on weekends).
    assert holidays_loaded(2099) is False
    assert is_trading_day(date(2099, 1, 3)) is False  # a Saturday
