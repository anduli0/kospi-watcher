"""News daily brief + morning briefing (offline; Telegram unconfigured)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.briefing.service import (
    format_brief_message,
    format_report_message,
    run_morning_briefing,
)
from kospi_watcher.infrastructure.news.mock import MockNewsProvider
from kospi_watcher.newsfeed.service import NewsService


async def test_daily_brief_is_news_digest(session: AsyncSession) -> None:
    svc = NewsService(provider=MockNewsProvider())
    await svc.scrape(session, topics=["코스피 증시", "삼성전자 반도체"], retention_days=14)
    brief = await svc.generate_daily_brief(session)

    assert brief.item_count >= 1
    assert brief.themes  # grouped by topic
    assert "종합" in brief.summary  # roundup style
    # No prediction yet -> market_read says so.
    assert "예측 리포트" in brief.market_read


async def test_morning_briefing_runs_without_telegram(session: AsyncSession) -> None:
    result = await run_morning_briefing(session)
    assert result.news_added >= 1  # mock news scraped
    assert result.prediction_direction in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert result.brief_items >= 1
    # Telegram is unconfigured in tests -> not sent, but no error raised.
    assert result.telegram_enabled is False
    assert "not configured" in result.telegram_report
    # The two artifacts are distinct and labeled.
    assert "예측 리포트" in result.report_message
    assert "뉴스 데일리 브리프" in result.brief_message


async def test_message_formatters_escape_and_label(session: AsyncSession) -> None:
    await run_morning_briefing(session)
    # Re-generate to grab the objects for direct formatting checks.
    from kospi_watcher.db import repositories
    from kospi_watcher.domain.news_brief import NewsBrief
    from kospi_watcher.domain.prediction.schemas import MarketPrediction

    pred_row = await repositories.get_latest_prediction(session)
    brief_row = await repositories.get_latest_daily_brief(session)
    assert pred_row is not None and brief_row is not None

    report = format_report_message(MarketPrediction.model_validate(pred_row.payload))
    brief = format_brief_message(NewsBrief.model_validate(brief_row.payload))
    assert "<b>" in report and "포지셔닝" in report
    assert "곱버스" in report
    assert "<b>" in brief
