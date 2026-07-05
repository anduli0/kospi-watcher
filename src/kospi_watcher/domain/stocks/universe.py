"""The stock-recommender candidate universe (ADR-026).

The recommender selects from a **broad** pool — the top ~300 KOSPI/KOSDAQ common
shares by market cap (``_universe_data.RAW_UNIVERSE``, a committed snapshot) —
not a hand-picked shortlist, so a pick actually means "best across the market".

A small set of structural leaders is hand-curated (``_CURATED``) with rich
metadata (structural ``themes``, ``rate_sensitivity``, ``beta``, news
``aliases``). For every other name the metadata is derived from its name/market
(coarse but reasonable), so broad names compete primarily on **real price
momentum / trend / sector / house view** while the curated leaders keep their
structural edge. Curated entries override the snapshot by code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kospi_watcher.domain.stocks._universe_data import RAW_UNIVERSE


@dataclass(frozen=True)
class StockMeta:
    code: str
    name: str
    yahoo: str
    sector_ko: str
    sector_key: str  # aligns to the market board's 8 keys where possible, else own
    themes: tuple[str, ...]
    rate_sensitivity: str  # "HIGH" (hurt by hikes) | "MED" | "LOW" | "BENEFIT" (banks)
    beta: str  # "HIGH" | "MED" | "LOW"
    aliases: tuple[str, ...] = field(default_factory=tuple)


# sector_key values that exist on the live sector board (analysis.py _SECTORS):
#   semiconductor, battery, bank, auto, bio, steel, transport, energychem
_CURATED: tuple[StockMeta, ...] = (
    StockMeta("005930", "삼성전자", "005930.KS", "반도체/IT", "semiconductor",
              ("AI반도체", "HBM", "파운드리"), "MED", "HIGH", ("삼성전자",)),
    StockMeta("000660", "SK하이닉스", "000660.KS", "반도체", "semiconductor",
              ("AI반도체", "HBM"), "MED", "HIGH", ("SK하이닉스", "하이닉스")),
    StockMeta("042700", "한미반도체", "042700.KS", "반도체장비", "semiconductor",
              ("HBM", "AI반도체"), "MED", "HIGH", ("한미반도체",)),
    StockMeta("009150", "삼성전기", "009150.KS", "전자부품", "semiconductor",
              ("MLCC", "AI", "전장"), "MED", "HIGH", ("삼성전기",)),
    StockMeta("051910", "LG화학", "051910.KS", "2차전지/화학", "battery",
              ("2차전지", "소재"), "HIGH", "HIGH", ("LG화학",)),
    StockMeta("006400", "삼성SDI", "006400.KS", "2차전지", "battery",
              ("2차전지", "ESS"), "HIGH", "HIGH", ("삼성SDI",)),
    StockMeta("247540", "에코프로비엠", "247540.KQ", "2차전지소재", "battery",
              ("2차전지", "양극재"), "HIGH", "HIGH", ("에코프로비엠",)),
    StockMeta("086520", "에코프로", "086520.KQ", "2차전지", "battery",
              ("2차전지",), "HIGH", "HIGH", ("에코프로",)),
    StockMeta("003670", "포스코퓨처엠", "003670.KS", "2차전지소재", "battery",
              ("2차전지", "양극재"), "HIGH", "HIGH", ("포스코퓨처엠",)),
    StockMeta("005490", "POSCO홀딩스", "005490.KS", "철강/소재", "steel",
              ("철강", "2차전지소재"), "MED", "MED", ("POSCO", "포스코홀딩스", "포스코")),
    StockMeta("010130", "고려아연", "010130.KS", "비철금속", "steel",
              ("비철금속", "2차전지소재"), "MED", "MED", ("고려아연",)),
    StockMeta("005380", "현대차", "005380.KS", "자동차", "auto",
              ("전기차", "자율주행"), "MED", "MED", ("현대차", "현대자동차")),
    StockMeta("000270", "기아", "000270.KS", "자동차", "auto",
              ("전기차",), "MED", "MED", ("기아",)),
    StockMeta("012330", "현대모비스", "012330.KS", "자동차부품", "auto",
              ("전장", "전기차"), "MED", "MED", ("현대모비스",)),
    StockMeta("207940", "삼성바이오로직스", "207940.KS", "바이오", "bio",
              ("CDMO", "바이오"), "HIGH", "HIGH", ("삼성바이오",)),
    StockMeta("068270", "셀트리온", "068270.KS", "바이오", "bio",
              ("바이오시밀러",), "HIGH", "HIGH", ("셀트리온",)),
    StockMeta("105560", "KB금융", "105560.KS", "금융", "bank",
              ("은행", "배당"), "BENEFIT", "LOW", ("KB금융",)),
    StockMeta("055550", "신한지주", "055550.KS", "금융", "bank",
              ("은행", "배당"), "BENEFIT", "LOW", ("신한지주", "신한")),
    StockMeta("086790", "하나금융지주", "086790.KS", "금융", "bank",
              ("은행", "배당"), "BENEFIT", "LOW", ("하나금융",)),
    StockMeta("035420", "NAVER", "035420.KS", "인터넷/플랫폼", "internet",
              ("AI", "플랫폼", "커머스"), "HIGH", "HIGH", ("네이버", "NAVER")),
    StockMeta("035720", "카카오", "035720.KS", "인터넷/플랫폼", "internet",
              ("플랫폼", "AI"), "HIGH", "HIGH", ("카카오",)),
    StockMeta("000720", "현대건설", "000720.KS", "건설", "construction",
              ("원전", "SMR", "인프라"), "HIGH", "MED", ("현대건설",)),
    StockMeta("034020", "두산에너빌리티", "034020.KS", "발전/기계", "power",
              ("원전", "SMR", "가스터빈"), "MED", "HIGH", ("두산에너빌리티", "두산")),
    StockMeta("015760", "한국전력", "015760.KS", "유틸리티", "utility",
              ("전력", "인프라"), "MED", "LOW", ("한국전력", "한전")),
    StockMeta("012450", "한화에어로스페이스", "012450.KS", "방산/항공", "defense",
              ("방산", "우주"), "MED", "HIGH", ("한화에어로",)),
    StockMeta("047810", "한국항공우주", "047810.KS", "방산/항공", "defense",
              ("방산", "항공"), "MED", "HIGH", ("한국항공우주", "KAI")),
    StockMeta("329180", "HD현대중공업", "329180.KS", "조선", "ship",
              ("조선", "방산"), "MED", "HIGH", ("HD현대중공업", "현대중공업")),
    StockMeta("042660", "한화오션", "042660.KS", "조선", "ship",
              ("조선", "방산"), "MED", "HIGH", ("한화오션",)),
    StockMeta("011200", "HMM", "011200.KS", "해운", "transport",
              ("해운", "물류"), "MED", "HIGH", ("HMM",)),
    StockMeta("003490", "대한항공", "003490.KS", "항공운송", "transport",
              ("항공", "여객"), "HIGH", "MED", ("대한항공",)),
)

STRUCTURAL_THEMES = frozenset(
    {"AI반도체", "HBM", "2차전지", "방산", "원전", "SMR", "조선", "CDMO", "AI", "플랫폼", "우주"}
)

# --- Metadata derivation for the broad (non-curated) names --------------------

# Korean label per sector key. The first 8 also exist on the live sector board.
_SECTOR_KO: dict[str, str] = {
    "semiconductor": "반도체/IT",
    "battery": "2차전지",
    "bank": "금융",
    "auto": "자동차",
    "bio": "바이오/제약",
    "steel": "철강/소재",
    "transport": "운송",
    "energychem": "화학/에너지",
    "construction": "건설",
    "ship": "조선/중공업",
    "defense": "방산/항공우주",
    "power": "전력/발전",
    "media": "미디어/엔터/게임",
    "internet": "인터넷/플랫폼",
    "consumer": "소비재/유통",
    "other": "기타",
}

# How BOK policy hits the sector (banks benefit from hikes; growth sectors hurt).
_RATE_BY_KEY: dict[str, str] = {
    "bank": "BENEFIT",
    "battery": "HIGH",
    "bio": "HIGH",
    "internet": "HIGH",
    "media": "HIGH",
    "construction": "HIGH",
}

# Keyword → sector key. Order matters (more specific first).
_SECTOR_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("battery", ("2차전지", "에너지솔루션", "양극재", "음극재", "에코프로", "엘앤에프", "배터리")),
    ("semiconductor", ("반도체", "파운드리", "HBM", "디스플레이")),
    ("bank", ("은행", "증권", "보험", "생명", "화재", "캐피탈", "카드", "금융")),
    ("auto", ("자동차", "모비스", "타이어")),
    ("bio", ("바이오", "제약", "파마", "셀트리온", "메디", "헬스", "진단", "신약")),
    ("steel", ("철강", "스틸", "포스코", "POSCO", "비철")),
    ("transport", ("항공", "해운", "물류", "운송", "택배")),
    ("ship", ("조선", "중공업")),
    ("defense", ("방산", "에어로", "항공우주")),
    ("power", ("전력", "발전", "에너빌리티", "터빈", "원전", "가스")),
    ("media", ("게임", "엔터", "미디어", "콘텐츠", "웹툰")),
    ("internet", ("인터넷", "플랫폼", "소프트", "네이버", "카카오")),
    ("energychem", ("화학", "케미칼", "정유", "석유", "에너지")),
    ("construction", ("건설", "엔지니어링", "건축")),
    ("consumer", ("식품", "유통", "백화점", "마트", "음료", "주류", "화장품", "패션")),
)


def _sector_key_from(name: str, sector_raw: str) -> str:
    hay = f"{name} {sector_raw}"
    for key, words in _SECTOR_KEYWORDS:
        if any(w in hay for w in words):
            return key
    return "other"


def _derive_meta(code: str, name: str, market: str, sector_raw: str) -> StockMeta:
    key = _sector_key_from(name, sector_raw)
    yahoo = f"{code}.KQ" if market == "KOSDAQ" else f"{code}.KS"
    return StockMeta(
        code=code,
        name=name,
        yahoo=yahoo,
        sector_ko=_SECTOR_KO.get(key, "기타"),
        sector_key=key,
        themes=(),  # structural-theme bonus is reserved for the curated leaders
        rate_sensitivity=_RATE_BY_KEY.get(key, "MED"),
        beta="HIGH" if market == "KOSDAQ" else "MED",
        aliases=(name,),
    )


def _build_universe() -> tuple[StockMeta, ...]:
    curated = {m.code: m for m in _CURATED}
    out: list[StockMeta] = []
    seen: set[str] = set()
    for code, name, market, sector_raw, _marcap in RAW_UNIVERSE:
        if code in seen:
            continue
        seen.add(code)
        out.append(curated.get(code) or _derive_meta(code, name, market, sector_raw))
    # Keep any curated leader that fell outside the snapshot's top-N.
    for meta in _CURATED:
        if meta.code not in seen:
            seen.add(meta.code)
            out.append(meta)
    return tuple(out)


STOCK_UNIVERSE: tuple[StockMeta, ...] = _build_universe()
