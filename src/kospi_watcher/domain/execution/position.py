"""Pure position & PnL math (Decimal only, ADR-008).

A position carries a *signed* quantity (long > 0, short < 0), an average cost per
unit of the absolute position, and cumulative realized PnL. ``apply_fill`` is a
pure function: given the prior state and a fill, it returns the new state and
folds realized PnL on the portion of the fill that reduces an existing position.
No I/O, no float.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kospi_watcher.domain.enums import OrderSide

_ZERO = Decimal("0")


@dataclass(frozen=True)
class PositionState:
    quantity: int = 0
    avg_cost: Decimal = _ZERO  # per unit of |quantity|; 0 when flat
    realized_pnl: Decimal = _ZERO

    def unrealized_pnl(self, mark_price: Decimal) -> Decimal:
        """Mark-to-market PnL at ``mark_price`` (signed by direction)."""
        return (mark_price - self.avg_cost) * Decimal(self.quantity)

    def market_value(self, mark_price: Decimal) -> Decimal:
        return mark_price * Decimal(self.quantity)


def apply_fill(
    state: PositionState, side: OrderSide, quantity: int, price: Decimal
) -> PositionState:
    """Apply one fill to ``state`` and return the new state.

    Increasing (or opening) recomputes the weighted-average cost. Reducing
    realizes PnL on the closed quantity; a fill that exceeds the existing size
    flips the position and re-bases the cost to the fill price for the remainder.
    """
    if quantity <= 0:
        raise ValueError("fill quantity must be positive")

    signed = quantity if side is OrderSide.BUY else -quantity
    prev_q = state.quantity
    new_q = prev_q + signed
    realized = state.realized_pnl

    same_direction = prev_q == 0 or (prev_q > 0) == (signed > 0)
    if same_direction:
        total_cost = abs(prev_q) * state.avg_cost + abs(signed) * price
        new_abs = abs(prev_q) + abs(signed)
        new_cost = total_cost / Decimal(new_abs) if new_abs else _ZERO
    else:
        closing = Decimal(min(abs(signed), abs(prev_q)))
        direction = Decimal(1) if prev_q > 0 else Decimal(-1)
        realized = realized + closing * (price - state.avg_cost) * direction
        if abs(signed) <= abs(prev_q):
            new_cost = _ZERO if new_q == 0 else state.avg_cost
        else:
            new_cost = price  # flipped: remainder opens at the fill price

    return PositionState(quantity=new_q, avg_cost=new_cost, realized_pnl=realized)
