"""POST /api/v1/notify/morning — run the daily briefing on demand.

Same pipeline the 08:00 worker cron runs (scrape → predict → news brief →
Telegram). Returns the rendered messages + Telegram delivery status, so it can be
used to preview/test the briefing without waiting for the cron or a bot token.
"""

from __future__ import annotations

from fastapi import APIRouter

from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.responses import MorningBriefingResponse
from kospi_watcher.briefing.service import run_morning_briefing

router = APIRouter(tags=["notify"])


@router.post("/notify/morning", response_model=MorningBriefingResponse)
async def trigger_morning_briefing(session: SessionDep) -> MorningBriefingResponse:
    result = await run_morning_briefing(session)
    return MorningBriefingResponse(
        news_added=result.news_added,
        prediction_direction=result.prediction_direction,
        brief_items=result.brief_items,
        telegram_enabled=result.telegram_enabled,
        telegram_report=result.telegram_report,
        telegram_brief=result.telegram_brief,
        report_message=result.report_message,
        brief_message=result.brief_message,
    )
