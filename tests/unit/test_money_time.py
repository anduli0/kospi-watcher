"""Money (no-float) and point-in-time datetime invariants — ADR-008 / ADR-009."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel

from kospi_watcher.domain.money import DecimalNoFloat, reject_float, to_decimal
from kospi_watcher.domain.time import KST, ensure_aware, now_utc, to_kst


class _PriceModel(BaseModel):
    price: DecimalNoFloat


def test_to_decimal_accepts_int_str_decimal() -> None:
    assert to_decimal(10) == Decimal("10")
    assert to_decimal("35000.50") == Decimal("35000.50")
    assert to_decimal(Decimal("1.25")) == Decimal("1.25")


def test_reject_float_raises() -> None:
    with pytest.raises(TypeError):
        reject_float(1.5)
    with pytest.raises(TypeError):
        to_decimal(1.5)  # type: ignore[arg-type]


def test_pydantic_decimal_field_rejects_float() -> None:
    # A raw float must never reach a price field (spec test #1). The
    # BeforeValidator raises TypeError, which Pydantic propagates (it only wraps
    # ValueError/AssertionError into ValidationError).
    with pytest.raises(TypeError):
        _PriceModel(price=35000.0)  # type: ignore[arg-type]
    assert _PriceModel(price=Decimal("35000")).price == Decimal("35000")
    assert _PriceModel(price="35000").price == Decimal("35000")


def test_ensure_aware_rejects_naive() -> None:
    naive = now_utc().replace(tzinfo=None)
    with pytest.raises(ValueError, match="naive datetime"):
        ensure_aware(naive)


def test_to_kst_offset_is_plus_nine() -> None:
    converted = to_kst(now_utc())
    assert converted.tzinfo == KST
    assert converted.utcoffset() is not None
    assert converted.utcoffset().total_seconds() == 9 * 3600  # type: ignore[union-attr]
