"""Morning briefing: refresh everything and push it to Telegram.

The daily 08:00 (Asia/Seoul) worker job runs :func:`run_morning_briefing`, which
(1) scrapes news, (2) generates+stores the prediction report, (3) builds+stores
the news daily brief, and (4) sends both to Telegram. It never raises; Telegram
failures (including "not configured") are returned, not thrown, so a missing bot
token simply means the data is refreshed but not pushed.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.agent_service.prediction import PredictionService
from kospi_watcher.db import repositories
from kospi_watcher.domain.enums import MarketDirection
from kospi_watcher.domain.market_calendar import closed_reason
from kospi_watcher.domain.news_brief import NewsBrief
from kospi_watcher.domain.prediction.regime import REGIME_KO
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.time import to_kst
from kospi_watcher.infrastructure.telegram import send_telegram_message
from kospi_watcher.newsfeed.service import NewsService

_DIR_KO = {
    MarketDirection.BULLISH: "강세",
    MarketDirection.BEARISH: "약세",
    MarketDirection.NEUTRAL: "중립",
}
_STANCE_KO = {
    "OVERWEIGHT": "비중확대",
    "NEUTRAL": "중립",
    "UNDERWEIGHT": "비중축소",
    "AVOID": "회피",
}
_BRIEFING_UNIVERSE = ("069500", "114800", "252670")


@dataclass(frozen=True)
class BriefingResult:
    news_added: int
    prediction_direction: str
    brief_items: int
    report_message: str
    brief_message: str
    telegram_report: str
    telegram_brief: str
    telegram_enabled: bool


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def format_report_message(p: MarketPrediction) -> str:
    by_symbol = {s.symbol: s for s in p.instrument_stances}

    def stance(sym: str) -> str:
        s = by_symbol.get(sym)
        return _STANCE_KO.get(s.label.value, s.label.value) if s else "-"

    chief = p.deliberation.chief.note if p.deliberation else ""
    as_of_kst = to_kst(p.as_of).date()
    date_str = as_of_kst.isoformat()
    # On a non-trading day, label this as a next-session forecast so "방향: 강세"
    # is never read as "the market rose today".
    reason = closed_reason(as_of_kst)
    closed_line = (
        f"🔕 오늘({date_str})은 {reason} — 아래는 다음 개장일 전망입니다.\n" if reason else ""
    )
    return (
        f"📈 <b>KOSPI 예측 리포트</b> · {date_str}\n"
        f"{closed_line}"
        f"대상: {_esc(p.subject)} · 기간: {_esc(p.horizon_label)}\n"
        f"방향: <b>{_DIR_KO[p.direction]}</b> · 확신 {p.confidence:.0%} · "
        f"{_esc(REGIME_KO.get(p.regime, p.regime.value))}\n"
        f"{_esc(p.headline)}\n\n"
        f"<b>포지셔닝</b>\n"
        f"• KODEX 200: {stance('069500')}\n"
        f"• 인버스: {stance('114800')}\n"
        f"• 곱버스(2X): {stance('252670')}\n\n"
        f"<i>{_esc(chief)}</i>"
    )


def format_brief_message(b: NewsBrief) -> str:
    header = f"📰 <b>뉴스 데일리 브리프</b> · {b.date}"
    if not b.is_trading_day:
        header += " · 🔕 휴장일"
    lines = [header, "", _esc(b.summary), ""]
    if b.key_points:
        lines.append("<b>📌 주요 뉴스</b>")
        for kp in b.key_points:
            lines.append(f"• [{_esc(kp.tag)}] {_esc(kp.title)} <i>({_esc(kp.source)})</i>")
        lines.append("")
    for theme in b.themes[:5]:
        lines.append(f"<b>{_esc(theme.topic)}</b> ({theme.count}건)")
        if theme.read:
            lines.append(f"<i>{_esc(theme.read)}</i>")
        for h in theme.headlines[:2]:
            lines.append(f"• {_esc(h.title)} <i>({_esc(h.source)})</i>")
        lines.append("")
    if b.market_read:
        lines.append(_esc(b.market_read))
    return "\n".join(lines).strip()


async def run_morning_briefing(session: AsyncSession) -> BriefingResult:
    news = await NewsService().scrape(session)

    headlines = await repositories.recent_headlines(session, limit=8)
    prediction = await PredictionService().generate(
        _BRIEFING_UNIVERSE, news_headlines=headlines
    )
    await repositories.save_prediction(session, prediction)
    await session.commit()

    brief = await NewsService().generate_daily_brief(session)

    report_msg = format_report_message(prediction)
    brief_msg = format_brief_message(brief)
    r1 = await send_telegram_message(report_msg)
    r2 = await send_telegram_message(brief_msg)

    return BriefingResult(
        news_added=news.added,
        prediction_direction=prediction.direction.value,
        brief_items=brief.item_count,
        report_message=report_msg,
        brief_message=brief_msg,
        telegram_report=r1.detail,
        telegram_brief=r2.detail,
        telegram_enabled=r1.ok or r2.ok,
    )
