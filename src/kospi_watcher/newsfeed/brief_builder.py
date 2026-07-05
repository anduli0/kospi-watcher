"""Build the news daily brief — a detailed morning briefing of the Korean stock
market built from the day's scraped headlines, NOT a bare list.

Deterministic and pure-ish: it groups the day's headlines by topic, then
*synthesizes* a multi-paragraph market briefing (today's tape → what the news
flow is saying, theme by theme → what to watch), surfaces the most notable
headlines as ``key_points``, gives every theme a one-line ``read``, and ties it
to the latest prediction's house view. The actual scraped headlines are the
substance; the prose organizes and interprets them.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from kospi_watcher.db import models
from kospi_watcher.domain.enums import MarketDirection, MarketRegime
from kospi_watcher.domain.market_calendar import is_trading_day_kst
from kospi_watcher.domain.news_brief import (
    NewsBrief,
    NewsHeadline,
    NewsKeyPoint,
    NewsTheme,
)
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.time import UTC, now_utc


def _aware(dt: datetime) -> datetime:
    """Coerce a DB datetime to UTC-aware (SQLite drops tzinfo)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


_PER_THEME = 6  # headlines kept per theme (the brief surfaces these)
_KEY_POINTS = 8  # notable headlines lifted into the highlights list

# Tone keywords scanned over headline titles (deterministic sentiment proxy).
_BULL_KW = (
    "급등", "상승", "돌파", "순매수", "강세", "호재", "최고", "신고가", "반등",
    "회복", "개선", "수혜", "기대", "랠리", "사상 최대", "흑자",
)
_BEAR_KW = (
    "급락", "하락", "약세", "순매도", "폭락", "우려", "부담", "칼바람", "경계",
    "둔화", "악재", "위축", "쇼크", "긴축", "위기", "적자", "불안",
)

# Plain-language gloss of the house direction.
_DIR_GLOSS: dict[MarketDirection, str] = {
    MarketDirection.BULLISH: "오를 가능성에 무게가 실린",
    MarketDirection.BEARISH: "내릴 가능성에 무게가 실린",
    MarketDirection.NEUTRAL: "뚜렷한 방향이 없는",
}

# Readable description of each market phase (no jargon).
_REGIME_PHRASE: dict[MarketRegime, str] = {
    MarketRegime.RISK_ON_STRONG: "위험자산 선호가 뚜렷한",
    MarketRegime.RISK_ON_FRAGILE: "위험을 선호하나 변동성이 큰",
    MarketRegime.LIQUIDITY_RALLY: "유동성에 기댄 상승",
    MarketRegime.EARNINGS_RALLY: "실적 기대가 이끄는 상승",
    MarketRegime.SIDEWAYS_LOW_VOL: "큰 변동 없이 방향을 탐색하는",
    MarketRegime.SIDEWAYS_HIGH_VOL: "변동성이 큰 채 방향이 엇갈리는",
    MarketRegime.RISK_OFF: "위험을 줄이려는 방어적인",
    MarketRegime.CRISIS: "위기 경계가 높은",
    MarketRegime.DATA_UNCERTAIN: "데이터가 불확실한",
}

# Short market angle per scraped topic (used in prose + key-point tags).
_THEME_ANGLE: dict[str, str] = {
    "코스피 증시": "지수 전반",
    "코스닥": "코스닥·중소형주",
    "원달러 환율": "원/달러 환율",
    "삼성전자 반도체": "반도체 대형주",
    "한국은행 기준금리": "금리 향방",
    "금융통화위원회": "통화정책(금통위)",
}

# One-line read of what each topic implies for the market.
_THEME_READ: dict[str, str] = {
    "코스피 증시": "지수 전반의 분위기와 대형주 흐름을 가늠하는 소식",
    "코스닥": "성장주·중소형주의 매기와 수급을 보여주는 소식",
    "원달러 환율": "환율 방향 — 외국인 자금 유출입을 좌우하는 핵심 변수",
    "삼성전자 반도체": "지수 비중이 큰 반도체 대형주 — 지수 방향을 좌우",
    "한국은행 기준금리": "금리 향방 — 성장주 밸류에이션과 직결되는 거시 변수",
    "금융통화위원회": "통화정책 신호 — 시장 방향을 가를 거시 이벤트",
}


def _angle(topic: str) -> str:
    return _THEME_ANGLE.get(topic, topic)


def _theme_read(topic: str, count: int) -> str:
    base = _THEME_READ.get(topic, f"{topic} 관련 소식")
    weight = "관심이 집중됐습니다" if count >= 6 else "꾸준히 보도됐습니다"
    return f"{base}. 관련 기사 {count}건으로 {weight}."


def _trim(text: str, limit: int = 64) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _connector(dominant_topic: str) -> str:
    """A one-line read of what the dominant news theme implies for the market."""
    if dominant_topic in ("원달러 환율",):
        return "환율이 외국인 수급의 핵심 변수로 부각된 하루였습니다."
    if dominant_topic in ("한국은행 기준금리", "금융통화위원회"):
        return "금리 향방에 시장의 관심이 쏠려 있어, 통화정책 신호가 방향을 가를 변수입니다."
    if dominant_topic in ("삼성전자 반도체",):
        return "지수 비중이 큰 반도체 대형주의 등락이 지수 방향을 좌우할 재료입니다."
    if dominant_topic in ("코스닥",):
        return "성장주·중소형주 쪽으로 매기가 옮겨갈지가 관전 포인트입니다."
    return "지수 분위기를 좌우할 재료들이 두루 섞인 흐름이었습니다."


def _watch_points(themes: list[NewsTheme]) -> str:
    """A closing 'what to watch' line driven by which topics dominated."""
    topics = {t.topic for t in themes[:4] if t.headlines}
    watch: list[str] = []
    if topics & {"한국은행 기준금리", "금융통화위원회"}:
        watch.append("금리·통화정책 일정")
    if "원달러 환율" in topics:
        watch.append("환율과 외국인 수급")
    if "삼성전자 반도체" in topics:
        watch.append("반도체 대형주 수급")
    if "코스닥" in topics:
        watch.append("코스닥 성장주 매기")
    if not watch:
        watch.append("외국인 수급과 거래대금")
    return "오늘 이후 관전 포인트는 " + ", ".join(watch) + "입니다."


def _investor_read(prediction: MarketPrediction | None, *, is_open: bool = True) -> str:
    """The sharp, actionable investor takeaway (the `market_read` line).

    Kept distinct from the narrative `summary`. When no prediction exists yet, it
    says so — and must mention '예측 리포트' (relied on by tests/UI). On a
    non-trading day the house view is labelled as the *next session*'s outlook,
    not "오늘의 종합 판단"."""
    if prediction is None:
        return (
            "투자자 관점 — 아직 오늘의 예측 리포트가 없어, "
            "방향보다는 뉴스 흐름을 참고하는 단계입니다."
        )
    action = {
        MarketDirection.BULLISH: (
            "지수형(KODEX 200)을 중심에 두되, 단기 급등과 외국인 매도 전환은 나눠 사며 대응하세요"
        ),
        MarketDirection.BEARISH: (
            "비중을 줄여 방어적으로 가져가되, "
            "곱버스(2배 인버스)의 장기 보유는 손실이 쌓이니 피하세요"
        ),
        MarketDirection.NEUTRAL: (
            "레버리지·인버스 모두 무리하지 말고, 방향이 확인된 뒤 비중을 조절하세요"
        ),
    }[prediction.direction]
    dir_ko = {
        MarketDirection.BULLISH: "강세",
        MarketDirection.BEARISH: "약세",
        MarketDirection.NEUTRAL: "중립",
    }[prediction.direction]
    judgment_label = "오늘의 종합 판단" if is_open else "다음 개장일 종합 판단"
    return (
        f"투자자 관점 — {action}. "
        f"({judgment_label}: 코스피 {dir_ko}, 확신도 {prediction.confidence:.0%})"
    )


def _tone_para(rows: Sequence[models.NewsItemRow]) -> str:
    """A paragraph reading the day's headline tone (bullish vs bearish wording)."""
    bull = sum(1 for r in rows if any(k in r.title for k in _BULL_KW))
    bear = sum(1 for r in rows if any(k in r.title for k in _BEAR_KW))
    if bull == 0 and bear == 0:
        return (
            "헤드라인에서 방향성을 가르는 표현이 두드러지지 않아, "
            "관망 분위기가 읽히는 하루였습니다."
        )
    if bull > bear * 1.3:
        body = f"상승·강세 톤({bull}건)이 하락·약세 톤({bear}건)을 앞섰습니다"
        tail = "전반적으로 위험선호 쪽으로 기운 분위기입니다."
    elif bear > bull * 1.3:
        body = f"하락·약세 톤({bear}건)이 상승·강세 톤({bull}건)을 앞섰습니다"
        tail = "전반적으로 경계심이 짙어진 분위기입니다."
    else:
        body = f"상승 톤({bull}건)과 하락 톤({bear}건)이 팽팽했습니다"
        tail = "방향을 두고 줄다리기가 이어진 분위기입니다."
    return f"오늘 수집한 헤드라인의 어조를 보면 {body} — {tail}"


def _flow_para(themes: list[NewsTheme]) -> str:
    """A paragraph weaving the top themes with their lead headlines."""
    top = [t for t in themes if t.headlines][:5]
    head = top[0]
    sent = [
        f"오늘 뉴스에서 가장 두드러진 흐름은 {_angle(head.topic)}입니다 — "
        f"'{_trim(head.headlines[0].title)}' 등 {head.count}건이 쏟아졌습니다."
    ]
    if len(top) > 1:
        parts = [
            f"{_angle(t.topic)}('{_trim(t.headlines[0].title, 38)}' 등 {t.count}건)"
            for t in top[1:]
        ]
        sent.append("이어 " + ", ".join(parts) + " 순으로 보도가 이어졌습니다.")
    sent.append(_connector(head.topic))
    return " ".join(sent)


def _summary(
    date_kst: str,
    rows: Sequence[models.NewsItemRow],
    themes: list[NewsTheme],
    prediction: MarketPrediction | None,
    *,
    is_open: bool = True,
) -> str:
    """The synthesized briefing narrative (four short paragraphs).

    On a non-trading day (weekend/휴장일) the lead does NOT assert a same-day
    market move — it states the market was closed and frames the house view as
    the next session's outlook."""
    # Paragraph 1 — today's tape at a glance (ties the count to the house view).
    if prediction is not None:
        phase = _REGIME_PHRASE.get(prediction.regime, "")
        outlook = f"{_DIR_GLOSS[prediction.direction]} {phase} 흐름"
        if is_open:
            lead = (
                f"오늘 한국 증시는 {outlook}입니다. "
                f"종합 판단을 한 줄로 옮기면 '{prediction.headline}'입니다."
            )
        else:
            lead = (
                f"다음 개장일 기준으로는 {outlook}이 예상됩니다. "
                f"종합 판단을 한 줄로 옮기면 '{prediction.headline}'입니다."
            )
    else:
        lead = "아직 오늘의 예측 리포트가 없어, 뉴스 흐름 위주로 정리합니다."
    opening = f"{date_kst} 한국 증시 데일리 브리핑입니다. "
    if not is_open:
        opening += "오늘은 증시 휴장일이라 거래는 없었습니다. "
    para1 = f"{opening}오늘 수집한 증시 뉴스 {len(rows)}건을 종합하면, {lead}"

    if not rows:
        return f"{para1} 다만 오늘 수집된 뉴스가 없어 세부 종합은 건너뜁니다."

    return "\n\n".join(
        [para1, _tone_para(rows), _flow_para(themes), _watch_points(themes)]
    )


def _key_points(themes: list[NewsTheme]) -> list[NewsKeyPoint]:
    """Surface notable, clickable headlines: the lead of each theme first, then
    deeper headlines from the busiest themes, up to the cap."""
    points: list[NewsKeyPoint] = []
    seen: set[str] = set()
    for depth in range(3):
        for t in themes:
            if len(t.headlines) <= depth:
                continue
            h = t.headlines[depth]
            if h.url in seen:
                continue
            seen.add(h.url)
            points.append(
                NewsKeyPoint(tag=_angle(t.topic), title=h.title, source=h.source, url=h.url)
            )
            if len(points) >= _KEY_POINTS:
                return points
    return points


def build_news_brief(
    date_kst: str,
    rows: Sequence[models.NewsItemRow],
    prediction: MarketPrediction | None,
    *,
    generated_by: str = "rule",
) -> NewsBrief:
    # Was the market open on this KST day? On a closed day the prose frames the
    # house view as the next session's outlook instead of a same-day move.
    is_open = is_trading_day_kst(date_kst)

    # Group by topic, newest first within each theme, themes ordered by volume.
    by_topic: dict[str, list[models.NewsItemRow]] = {}
    for row in sorted(rows, key=lambda r: r.published_at, reverse=True):
        by_topic.setdefault(row.topic, []).append(row)

    themes = [
        NewsTheme(
            topic=topic,
            count=len(items),
            read=_theme_read(topic, len(items)),
            headlines=[
                NewsHeadline(
                    title=it.title,
                    source=it.source,
                    url=it.url,
                    published_at=_aware(it.published_at),
                )
                for it in items[:_PER_THEME]
            ],
        )
        for topic, items in sorted(by_topic.items(), key=lambda kv: len(kv[1]), reverse=True)
    ]

    return NewsBrief(
        date=date_kst,
        item_count=len(rows),
        is_trading_day=is_open,
        summary=_summary(date_kst, rows, themes, prediction, is_open=is_open),
        market_read=_investor_read(prediction, is_open=is_open),
        key_points=_key_points(themes),
        themes=themes,
        generated_by=generated_by,
        created_at=now_utc(),
    )
