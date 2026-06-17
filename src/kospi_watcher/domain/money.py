"""Decimal money/price helpers (see ADR-008).

``float`` is forbidden for any monetary or price value. Use :data:`DecimalNoFloat`
for Pydantic fields and :func:`to_decimal` in plain code; both reject ``float``
inputs so rounding error can never enter a price or notional.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BeforeValidator

KRW = "KRW"


def reject_float(value: object) -> object:
    """Pydantic ``BeforeValidator`` hook: raise if a raw ``float`` is supplied."""
    if isinstance(value, float):
        raise TypeError(
            "float is not allowed for monetary or price values; "
            "use Decimal, int, or a numeric string instead"
        )
    return value


def to_decimal(value: int | str | Decimal) -> Decimal:
    """Coerce an int / numeric-string / Decimal to Decimal. Rejects float."""
    if isinstance(value, float):  # defensive; mirrors reject_float
        raise TypeError("float is not allowed for monetary or price values")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"cannot parse Decimal from {value!r}") from exc


# A Pydantic-usable Decimal that rejects ``float`` at validation time.
DecimalNoFloat = Annotated[Decimal, BeforeValidator(reject_float)]
