"""Mandated trading-safety defaults must hold and must require multiple gates."""

from __future__ import annotations

from kospi_watcher.config import LIVE_EXECUTION_IMPLEMENTED, Settings
from kospi_watcher.domain.enums import TradingMode


def test_safety_defaults() -> None:
    s = Settings()
    assert s.trading_mode is TradingMode.RESEARCH
    assert s.live_trading_enabled is False
    assert s.auto_execution_enabled is False


def test_live_execution_not_implemented_in_this_phase() -> None:
    assert LIVE_EXECUTION_IMPLEMENTED is False


def test_arming_requires_multiple_independent_gates() -> None:
    # A single flag is never enough to arm live or auto execution.
    only_flag = Settings(live_trading_enabled=True)
    assert only_flag.live_execution_armed is False  # still RESEARCH mode

    live = Settings(live_trading_enabled=True, trading_mode=TradingMode.GUARDED_LIVE)
    assert live.live_execution_armed is True
    assert live.auto_execution_armed is False  # GUARDED_LIVE never auto-sends

    auto = Settings(
        live_trading_enabled=True,
        auto_execution_enabled=True,
        trading_mode=TradingMode.AUTO_LIVE,
    )
    assert auto.auto_execution_armed is True
