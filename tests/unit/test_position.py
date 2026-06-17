"""Position & PnL math (pure, Decimal)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kospi_watcher.domain.enums import OrderSide
from kospi_watcher.domain.execution.position import PositionState, apply_fill


def test_open_long() -> None:
    s = apply_fill(PositionState(), OrderSide.BUY, 10, Decimal("35000"))
    assert s.quantity == 10
    assert s.avg_cost == Decimal("35000")
    assert s.realized_pnl == Decimal("0")


def test_increase_uses_weighted_average() -> None:
    s = apply_fill(PositionState(10, Decimal("100")), OrderSide.BUY, 10, Decimal("200"))
    assert s.quantity == 20
    assert s.avg_cost == Decimal("150")


def test_partial_close_realizes_pnl() -> None:
    s = apply_fill(PositionState(10, Decimal("100")), OrderSide.SELL, 4, Decimal("150"))
    assert s.quantity == 6
    assert s.avg_cost == Decimal("100")  # cost basis unchanged on reduce
    assert s.realized_pnl == Decimal("200")  # 4 * (150 - 100)


def test_full_close_goes_flat() -> None:
    s = apply_fill(PositionState(10, Decimal("100")), OrderSide.SELL, 10, Decimal("120"))
    assert s.quantity == 0
    assert s.avg_cost == Decimal("0")
    assert s.realized_pnl == Decimal("200")


def test_oversell_flips_to_short_and_rebases() -> None:
    s = apply_fill(PositionState(5, Decimal("100")), OrderSide.SELL, 8, Decimal("120"))
    assert s.quantity == -3
    assert s.avg_cost == Decimal("120")  # remainder opens short at the fill price
    assert s.realized_pnl == Decimal("100")  # 5 * (120 - 100)


def test_unrealized_pnl_signed() -> None:
    assert PositionState(10, Decimal("100")).unrealized_pnl(Decimal("130")) == Decimal("300")
    assert PositionState(-10, Decimal("100")).unrealized_pnl(Decimal("130")) == Decimal("-300")


def test_zero_quantity_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        apply_fill(PositionState(), OrderSide.BUY, 0, Decimal("1"))
