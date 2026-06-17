"""Custom SQLAlchemy column types.

``DecimalString`` stores a ``Decimal`` as TEXT so precision is preserved
identically on SQLite (local/CI) and Postgres (prod). This avoids SQLite's
float-backed NUMERIC, which would silently round money/price values (refines
ADR-008).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Dialect, String
from sqlalchemy.types import TypeDecorator

from kospi_watcher.domain.money import to_decimal


class DecimalString(TypeDecorator[Decimal]):
    impl = String
    cache_ok = True

    def __init__(self, length: int = 32, **kw: Any) -> None:
        super().__init__(length=length, **kw)

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return str(to_decimal(value))

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return Decimal(value)
