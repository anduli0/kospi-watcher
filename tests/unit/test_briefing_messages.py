"""Telegram message formatters flag 휴장 and frame the forecast as next-session."""

from __future__ import annotations

from datetime import datetime

from kospi_watcher.briefing.service import format_brief_message, format_report_message
from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.registry import AgentRegistry
from kospi_watcher.domain.prediction.synthesizer import synthesize
from kospi_watcher.domain.time import UTC, now_utc
from kospi_watcher.newsfeed.brief_builder import build_news_brief

# 2026-06-20 12:00 KST (03:00 UTC) — a Saturday → market closed.
_SAT_UTC = datetime(2026, 6, 20, 3, 0, tzinfo=UTC)
# 2026-06-19 12:00 KST (03:00 UTC) — a Friday → market open.
_FRI_UTC = datetime(2026, 6, 19, 3, 0, tzinfo=UTC)


def _prediction(as_of: datetime):
    findings = [
        f
        for r in AgentRegistry().run_all(
            AgentContext(as_of=now_utc(), universe=("069500",))
        )
        for f in r.findings
    ]
    return synthesize(findings, generated_by="mock", as_of=as_of)


def test_report_message_flags_closed_day() -> None:
    report = format_report_message(_prediction(_SAT_UTC))
    assert "다음 개장일 전망" in report
    assert "휴장" in report or "주말" in report


def test_report_message_open_day_has_no_holiday_note() -> None:
    report = format_report_message(_prediction(_FRI_UTC))
    assert "다음 개장일 전망" not in report
    assert "🔕" not in report


def test_brief_message_header_badges_holiday() -> None:
    brief = build_news_brief("2026-06-20", [], None)  # Saturday
    assert "🔕 휴장일" in format_brief_message(brief)
    open_brief = build_news_brief("2026-06-19", [], None)  # Friday
    assert "🔕 휴장일" not in format_brief_message(open_brief)
