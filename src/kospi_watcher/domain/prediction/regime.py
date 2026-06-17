"""Deterministic mapping of aggregate signals to one of the 9 market regimes."""

from __future__ import annotations

from kospi_watcher.domain.agents.org import Desk
from kospi_watcher.domain.enums import MarketDirection, MarketRegime

_HIGH = 0.55

REGIME_KO: dict[MarketRegime, str] = {
    MarketRegime.RISK_ON_STRONG: "강한 위험선호",
    MarketRegime.RISK_ON_FRAGILE: "취약한 위험선호",
    MarketRegime.LIQUIDITY_RALLY: "유동성 랠리",
    MarketRegime.EARNINGS_RALLY: "실적 랠리",
    MarketRegime.SIDEWAYS_LOW_VOL: "저변동성 횡보",
    MarketRegime.SIDEWAYS_HIGH_VOL: "고변동성 횡보",
    MarketRegime.RISK_OFF: "위험회피",
    MarketRegime.CRISIS: "위기",
    MarketRegime.DATA_UNCERTAIN: "데이터 불확실",
}


def classify_regime(
    *,
    direction: MarketDirection,
    confidence: float,
    vol_high: bool,
    risk_high: bool,
    data_ok: bool,
    top_desk: Desk | None,
) -> MarketRegime:
    if not data_ok:
        return MarketRegime.DATA_UNCERTAIN

    if direction is MarketDirection.BEARISH:
        if risk_high and confidence >= _HIGH:
            return MarketRegime.CRISIS
        return MarketRegime.RISK_OFF

    if direction is MarketDirection.BULLISH:
        if confidence >= _HIGH and not vol_high:
            return MarketRegime.RISK_ON_STRONG
        if vol_high:
            return MarketRegime.RISK_ON_FRAGILE
        if top_desk is Desk.FUNDAMENTAL:
            return MarketRegime.EARNINGS_RALLY
        return MarketRegime.LIQUIDITY_RALLY

    # NEUTRAL
    return MarketRegime.SIDEWAYS_HIGH_VOL if vol_high else MarketRegime.SIDEWAYS_LOW_VOL
