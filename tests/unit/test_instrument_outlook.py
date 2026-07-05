"""Unit tests for the per-instrument outlook model (ADR-023).

Verifies verdict direction, price-target ordering, leverage decay growth, the
missing-price path, and full-ladder report coverage. Pure & deterministic.
"""

from __future__ import annotations

from decimal import Decimal

from kospi_watcher.domain.enums import (
    InstrumentKind,
    MarketDirection,
    MarketRegime,
)
from kospi_watcher.domain.prediction.instrument_outlook import (
    PositionVerdict,
    build_outlook,
    build_report,
)
from kospi_watcher.domain.time import now_utc


def test_bearish_makes_inverse_buy_and_long_sell() -> None:
    long1 = build_outlook(
        "069500", "KODEX 200", InstrumentKind.LONG_1X, Decimal("142000"), "yahoo",
        MarketDirection.BEARISH, 0.7, MarketRegime.RISK_OFF,
    )
    inv1 = build_outlook(
        "114800", "KODEX 인버스", InstrumentKind.INVERSE_1X, Decimal("4200"), "yahoo",
        MarketDirection.BEARISH, 0.7, MarketRegime.RISK_OFF,
    )
    assert long1.verdict == PositionVerdict.SELL
    assert inv1.verdict == PositionVerdict.BUY
    # On a bearish view the long product falls, the inverse rises (short horizon).
    assert long1.projections[0].expected_return_pct < 0
    assert inv1.projections[0].expected_return_pct > 0


def test_price_targets_are_ordered() -> None:
    o = build_outlook(
        "069500", "KODEX 200", InstrumentKind.LONG_1X, Decimal("142000"), "yahoo",
        MarketDirection.BULLISH, 0.8, MarketRegime.RISK_ON_STRONG,
    )
    for p in o.projections:
        assert p.target_low is not None
        assert p.target_base is not None
        assert p.target_high is not None
        assert p.target_low < p.target_base < p.target_high


def test_leverage_decay_worsens_with_horizon() -> None:
    # 2x long in a sideways high-vol regime: with ~0 drift, decay drag deepens
    # as the horizon lengthens (short > mid > long expected return).
    o = build_outlook(
        "122630", "KODEX 레버리지", InstrumentKind.LONG_2X, Decimal("219000"), "yahoo",
        MarketDirection.NEUTRAL, 0.5, MarketRegime.SIDEWAYS_HIGH_VOL,
    )
    rets = [p.expected_return_pct for p in o.projections]  # short, mid, long
    assert rets[0] > rets[1] > rets[2]
    assert o.risk_note is not None  # leverage decay note present


def test_missing_price_yields_no_targets() -> None:
    o = build_outlook(
        "069500", "KODEX 200", InstrumentKind.LONG_1X, None, "none",
        MarketDirection.BULLISH, 0.7, MarketRegime.RISK_ON_STRONG,
    )
    assert all(p.target_base is None for p in o.projections)
    assert o.current_price is None


def test_report_covers_full_ladder() -> None:
    prices: dict[str, tuple[Decimal | None, str]] = {
        "069500": (Decimal("142000"), "yahoo"),
        "122630": (Decimal("219000"), "yahoo"),
        "114800": (Decimal("4200"), "yahoo"),
        "252670": (Decimal("68"), "yahoo"),
    }
    r = build_report(
        MarketDirection.BULLISH, 0.6, MarketRegime.RISK_ON_STRONG, "mock",
        prices, now_utc(),
    )
    assert len(r.instruments) == 4
    assert r.price_source == "yahoo"
    long1 = next(i for i in r.instruments if i.symbol == "069500")
    assert long1.verdict == PositionVerdict.BUY  # bullish → buy the 1x long
    assert all(len(i.projections) == 3 for i in r.instruments)
