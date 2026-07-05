"""News daily-brief prose adapts to trading vs non-trading (휴장) days."""

from __future__ import annotations

from kospi_watcher.db import models
from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.registry import AgentRegistry
from kospi_watcher.domain.prediction.synthesizer import synthesize
from kospi_watcher.domain.time import now_utc
from kospi_watcher.newsfeed.brief_builder import build_news_brief


def _rows(date_kst: str, n: int = 3) -> list[models.NewsItemRow]:
    ts = now_utc()
    return [
        models.NewsItemRow(
            id=f"id-{i}",
            title=f"코스피 상승 기대 헤드라인 {i}",
            url=f"https://example.com/{i}",
            source="테스트",
            topic="코스피 증시",
            published_at=ts,
            date_kst=date_kst,
            summary=None,
            created_at=ts,
        )
        for i in range(n)
    ]


def _prediction():
    findings = [
        f
        for r in AgentRegistry().run_all(
            AgentContext(as_of=now_utc(), universe=("069500",))
        )
        for f in r.findings
    ]
    return synthesize(findings, generated_by="mock")


def test_trading_day_brief_speaks_in_present_tense() -> None:
    pred = _prediction()
    brief = build_news_brief("2026-06-19", _rows("2026-06-19"), pred)  # Friday
    assert brief.is_trading_day is True
    assert "오늘 한국 증시는" in brief.summary
    assert "휴장" not in brief.summary
    assert "다음 개장일" not in brief.market_read


def test_holiday_brief_does_not_assert_a_same_day_move() -> None:
    pred = _prediction()
    brief = build_news_brief("2026-06-20", _rows("2026-06-20"), pred)  # Saturday
    assert brief.is_trading_day is False
    # Must NOT claim the market moved today...
    assert "오늘 한국 증시는" not in brief.summary
    # ...must say it was closed, and frame the view as the next session.
    assert "휴장일" in brief.summary
    assert "다음 개장일" in brief.summary
    assert "다음 개장일 종합 판단" in brief.market_read


def test_holiday_brief_without_prediction_still_flags_closure() -> None:
    brief = build_news_brief("2026-06-20", _rows("2026-06-20"), None)  # Saturday
    assert brief.is_trading_day is False
    assert "휴장일" in brief.summary
    # No prediction → market_read still points at the missing 예측 리포트.
    assert "예측 리포트" in brief.market_read
