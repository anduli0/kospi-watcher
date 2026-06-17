"""News endpoints: dated headlines + scrape trigger.

GET  /news          — recent items (optionally ?date=YYYY-MM-DD)
GET  /news/dates    — available dates with counts
POST /news/scrape   — fetch the configured topics, store new, prune old
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.responses import (
    NewsDateCount,
    NewsDatesResponse,
    NewsItemResponse,
    NewsListResponse,
    ScrapeResponse,
)
from kospi_watcher.db import repositories
from kospi_watcher.domain.news_brief import NewsBrief
from kospi_watcher.newsfeed.service import NewsService

router = APIRouter(tags=["news"])
_service = NewsService()


@router.get("/news/brief", response_model=NewsBrief)
async def latest_daily_brief(session: SessionDep) -> NewsBrief:
    row = await repositories.get_latest_daily_brief(session)
    if row is None:
        raise HTTPException(status_code=404, detail="no brief yet; POST /news/brief/run")
    return NewsBrief.model_validate(row.payload)


@router.post("/news/brief/run", response_model=NewsBrief)
async def run_daily_brief(session: SessionDep) -> NewsBrief:
    return await _service.generate_daily_brief(session)


@router.get("/news", response_model=NewsListResponse)
async def list_news(
    session: SessionDep,
    date: str | None = Query(default=None, description="KST date YYYY-MM-DD"),
    limit: int = Query(default=50, ge=1, le=200),
) -> NewsListResponse:
    rows = await repositories.list_news(session, date_kst=date, limit=limit)
    return NewsListResponse(
        count=len(rows),
        date=date,
        items=[
            NewsItemResponse(
                id=r.id,
                title=r.title,
                url=r.url,
                source=r.source,
                topic=r.topic,
                published_at=r.published_at,
                date_kst=r.date_kst,
            )
            for r in rows
        ],
    )


@router.get("/news/dates", response_model=NewsDatesResponse)
async def news_dates(session: SessionDep) -> NewsDatesResponse:
    rows = await repositories.news_dates(session)
    return NewsDatesResponse(dates=[NewsDateCount(date=d, count=c) for d, c in rows])


@router.post("/news/scrape", response_model=ScrapeResponse)
async def scrape_news(session: SessionDep) -> ScrapeResponse:
    result = await _service.scrape(session)
    return ScrapeResponse(
        fetched=result.fetched,
        added=result.added,
        pruned=result.pruned,
        topics=result.topics,
    )
