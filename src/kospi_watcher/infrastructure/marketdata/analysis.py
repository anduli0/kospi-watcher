"""Builds the 'what moved KOSPI today' board (ADR-022).

Two parts, sourced honestly:

* **Sector moves** — live, keyless % change for a basket of KODEX *sector* ETFs
  via the same Yahoo chart endpoint used by :mod:`...marketdata.yahoo`. Never
  raises; any sector that fails to fetch degrades to a labelled offline value.
* **Investor flows (외국인/기관/개인)** — there is no keyless real-time KRX feed,
  so these are **representative**: deterministically derived from the index move
  and the KST date, labelled ``source="representative"`` so they can never be
  mistaken for a real KRX print. The three groups net to ~0 each day, mirroring
  the zero-sum nature of exchange flow. Wire a real KRX/pykrx feed here later.

Results are cached for a short TTL so a page refresh does not hammer Yahoo.
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from kospi_watcher.config import get_settings
from kospi_watcher.domain.market_analysis.schemas import (
    InvestorFlow,
    InvestorTrendPoint,
    MarketAnalysis,
    SectorMove,
)
from kospi_watcher.domain.money import to_decimal
from kospi_watcher.domain.time import now_utc, to_kst

_YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
_INDEX_YSYM = "^KS11"
_TWO = Decimal("0.01")

# Representative KODEX sector ETFs (code, Yahoo symbol, Korean name, english key).
_SECTORS: tuple[tuple[str, str, str, str], ...] = (
    ("091160", "091160.KS", "반도체", "semiconductor"),
    ("305720", "305720.KS", "2차전지", "battery"),
    ("091170", "091170.KS", "은행", "bank"),
    ("091180", "091180.KS", "자동차", "auto"),
    ("244580", "244580.KS", "바이오", "bio"),
    ("117680", "117680.KS", "철강", "steel"),
    ("140710", "140710.KS", "운송", "transport"),
    ("117460", "117460.KS", "에너지화학", "energychem"),
)

# Plausible offline base prices (KRW) for the mock branch / fetch failures.
_MOCK_PRICE: dict[str, Decimal] = {
    "091160": Decimal("38000"),
    "305720": Decimal("14500"),
    "091170": Decimal("9800"),
    "091180": Decimal("18500"),
    "244580": Decimal("9200"),
    "117680": Decimal("12500"),
    "140710": Decimal("11800"),
    "117460": Decimal("9600"),
}

_INVESTORS: tuple[tuple[str, str, int, int], ...] = (
    # investor, label, magnitude low, magnitude high (억원)
    ("FOREIGN", "외국인", 1500, 6000),
    ("INSTITUTION", "기관", 1000, 4500),
)


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_TWO, rounding=ROUND_HALF_UP)


class MarketAnalysisService:
    """Assembles :class:`MarketAnalysis`. Live sectors + representative flows."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        ttl_seconds: int = 120,
        offline: bool | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._owns_client = client is None
        self._ttl = ttl_seconds
        self._ua = settings.market_data_user_agent
        # Offline (mock) when explicitly asked or when the quote provider is mock.
        self._offline = (
            offline if offline is not None else settings.market_data_provider != "yahoo"
        )
        self._cache: tuple[float, MarketAnalysis] | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=8.0)
        return self._client

    async def build(self) -> MarketAnalysis:
        now = time.monotonic()
        if self._cache is not None and self._cache[0] > now:
            return self._cache[1]
        analysis = await self._build_fresh()
        self._cache = (now + self._ttl, analysis)
        return analysis

    async def _build_fresh(self) -> MarketAnalysis:
        as_of = now_utc()
        kst = to_kst(as_of)
        index_price: Decimal | None
        index_chg: Decimal | None
        if self._offline:
            index_price, index_chg = self._mock_index(kst)
            sectors = self._mock_sectors(kst)
            sector_source = "mock"
        else:
            index_price, index_chg, sectors, sector_source = await self._live_board()

        sectors.sort(key=lambda s: s.change_pct, reverse=True)
        leaders = [s for s in sectors if s.change_pct > 0][:3]
        laggards = [s for s in sectors if s.change_pct < 0][-3:][::-1]

        flows = _representative_flows(index_chg, kst)
        flow_source = flows[0].source if flows else "representative"
        narrative = _narrative(index_chg, leaders, laggards, flows)

        return MarketAnalysis(
            as_of=as_of,
            index_symbol="KOSPI",
            index_price=index_price,
            index_change_pct=index_chg,
            sectors=sectors,
            leaders=leaders,
            laggards=laggards,
            flows=flows,
            narrative=narrative,
            sector_source=sector_source,
            flow_source=flow_source,
        )

    # --- live (Yahoo) ---

    async def _live_board(
        self,
    ) -> tuple[Decimal | None, Decimal | None, list[SectorMove], str]:
        client = await self._get_client()
        index_task = self._fetch(client, _INDEX_YSYM)
        sector_tasks = [self._fetch(client, ysym) for _, ysym, _, _ in _SECTORS]
        index_res, *sector_res = await asyncio.gather(index_task, *sector_tasks)

        index_price, index_chg = index_res
        sectors: list[SectorMove] = []
        live_count = 0
        for (code, _ysym, name, key), (price, chg) in zip(
            _SECTORS, sector_res, strict=True
        ):
            if price is not None and chg is not None:
                live_count += 1
                sectors.append(
                    SectorMove(
                        key=key,
                        name=name,
                        symbol=code,
                        price=price,
                        change_pct=chg,
                        source="yahoo",
                    )
                )
            else:  # degrade this sector to a labelled offline value
                mprice, mchg = self._mock_one(code)
                sectors.append(
                    SectorMove(
                        key=key,
                        name=name,
                        symbol=code,
                        price=mprice,
                        change_pct=mchg,
                        source="mock",
                    )
                )
        source = "yahoo" if live_count >= len(_SECTORS) // 2 else "mock"
        return index_price, index_chg, sectors, source

    async def _fetch(
        self, client: httpx.AsyncClient, ysym: str
    ) -> tuple[Decimal | None, Decimal | None]:
        """Return (price, signed % change) or (None, None). Never raises."""
        try:
            resp = await client.get(
                _YAHOO_BASE + ysym,
                params={"interval": "1d", "range": "1d"},
                headers={"User-Agent": self._ua},
            )
            if resp.status_code != 200:
                return None, None
            return self._parse(resp.json())
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None, None

    @staticmethod
    def _parse(payload: dict[str, Any]) -> tuple[Decimal | None, Decimal | None]:
        result = payload.get("chart", {}).get("result")
        if not result:
            return None, None
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        # Official prior-session close gives the correct *daily* % change;
        # chartPreviousClose depends on the requested range, so only fall back to it.
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        if price is None or not prev:
            return None, None
        p = to_decimal(str(price))
        pv = to_decimal(str(prev))
        if pv == 0:
            return p, None
        return p, _q2((p - pv) / pv * Decimal("100"))

    # --- offline (mock) ---

    def _mock_index(self, kst: Any) -> tuple[Decimal, Decimal]:
        rng = random.Random(int(kst.strftime("%Y%m%d")) + 11)  # noqa: S311 (non-crypto)
        chg = _q2(to_decimal(str(rng.uniform(-1.4, 1.4))))
        base = Decimal("2700")
        price = _q2(base * (Decimal("1") + chg / Decimal("100")))
        return price, chg

    def _mock_sectors(self, kst: Any) -> list[SectorMove]:
        moves: list[SectorMove] = []
        for code, _ysym, name, key in _SECTORS:
            price, chg = self._mock_one(code, kst)
            moves.append(
                SectorMove(
                    key=key, name=name, symbol=code, price=price, change_pct=chg,
                    source="mock",
                )
            )
        return moves

    def _mock_one(self, code: str, kst: Any | None = None) -> tuple[Decimal, Decimal]:
        seed = code if kst is None else f"{code}{kst.strftime('%Y%m%d')}"
        rng = random.Random(hash(seed) & 0xFFFFFFFF)  # noqa: S311 (non-crypto)
        chg = _q2(to_decimal(str(rng.uniform(-2.6, 2.6))))
        base = _MOCK_PRICE.get(code, Decimal("10000"))
        price = _q2(base * (Decimal("1") + chg / Decimal("100")))
        return price, chg

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


def _representative_flows(
    index_chg: Decimal | None, kst: Any
) -> list[InvestorFlow]:
    """Deterministic, clearly-labelled 외국인/기관/개인 net flow (억원).

    The three groups net to ~0 each day (individuals are the counterparty to
    foreign+institution). Today's sign for foreign tracks the index move so the
    narrative stays coherent. NOT a real KRX print — ``source="representative"``.
    """
    rng = random.Random(int(kst.strftime("%Y%m%d")) + 7)  # noqa: S311 (non-crypto)
    bias = 0
    if index_chg is not None:
        bias = 1 if index_chg > 0 else -1 if index_chg < 0 else 0

    dates = [(kst - timedelta(days=4 - k)).strftime("%Y-%m-%d") for k in range(5)]

    def series(lo: int, hi: int) -> list[Decimal]:
        out: list[Decimal] = []
        for k in range(5):
            mag = Decimal(rng.randint(lo, hi))
            if k == 4 and bias != 0:
                sign = bias
            else:
                sign = 1 if rng.random() > 0.45 else -1
            out.append(mag * sign)
        return out

    foreign = series(1500, 6000)
    institution = series(1000, 4500)
    # Individuals take the other side, plus small residual noise.
    individual = [
        -(foreign[k] + institution[k]) + Decimal(rng.randint(-400, 400))
        for k in range(5)
    ]

    def flow(investor: str, label: str, vals: list[Decimal]) -> InvestorFlow:
        return InvestorFlow(
            investor=investor,
            label=label,
            net_today=vals[4],
            net_5d=sum(vals, Decimal("0")),
            trend=[
                InvestorTrendPoint(date=d, net=v)
                for d, v in zip(dates, vals, strict=True)
            ],
            source="representative",
        )

    return [
        flow("FOREIGN", "외국인", foreign),
        flow("INSTITUTION", "기관", institution),
        flow("INDIVIDUAL", "개인", individual),
    ]


def _fmt_net(net: Decimal) -> str:
    word = "순매수" if net > 0 else "순매도" if net < 0 else "중립"
    return f"{word} {abs(int(net)):,}억"


def _narrative(
    index_chg: Decimal | None,
    leaders: list[SectorMove],
    laggards: list[SectorMove],
    flows: list[InvestorFlow],
) -> str:
    if index_chg is None:
        head = "코스피 지수 변동 정보 없음."
    elif index_chg > 0:
        head = f"코스피 +{index_chg}% 상승."
    elif index_chg < 0:
        head = f"코스피 {index_chg}% 하락."
    else:
        head = "코스피 보합."
    lead_s = " · ".join(s.name for s in leaders) or "—"
    lag_s = " · ".join(s.name for s in laggards) or "—"
    flow_s = " · ".join(f"{f.label} {_fmt_net(f.net_today)}" for f in flows)
    return f"{head} {lead_s} 강세, {lag_s} 약세 주도. {flow_s}."


_service: MarketAnalysisService | None = None


def get_market_analysis_service() -> MarketAnalysisService:
    global _service
    if _service is None:
        _service = MarketAnalysisService()
    return _service


async def reset_market_analysis_service() -> None:
    global _service
    if _service is not None:
        await _service.aclose()
    _service = None
