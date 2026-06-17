"""The isolated Execution Gateway."""

from __future__ import annotations

from kospi_watcher.config import (
    LIVE_EXECUTION_IMPLEMENTED,
    PAPER_EXECUTION_IMPLEMENTED,
    get_settings,
)
from kospi_watcher.domain.execution.broker import (
    ApprovedOrder,
    BrokerAdapter,
    BrokerOrder,
    MockBrokerAdapter,
)


class GatewayBlockedError(RuntimeError):
    """Raised if a submission is attempted that the current gates do not allow."""


class ExecutionGateway:
    """Wraps a single :class:`BrokerAdapter`. Only this class calls
    ``submit_order`` outside the broker module itself.

    Simulated brokers (MOCK / PAPER) move no real money and are always allowed
    (PAPER additionally requires ``PAPER_EXECUTION_IMPLEMENTED``). A real/live
    broker is blocked unless live execution is implemented AND armed — which it
    is not in this phase."""

    def __init__(self, broker: BrokerAdapter | None = None) -> None:
        self._broker: BrokerAdapter = broker or MockBrokerAdapter()

    @property
    def broker_mode(self) -> str:
        return getattr(self._broker, "mode", "UNKNOWN")

    async def submit(self, order: ApprovedOrder) -> BrokerOrder:
        mode = getattr(self._broker, "mode", None)
        if mode == "MOCK":
            return await self._broker.submit_order(order)
        if mode == "PAPER":
            if not PAPER_EXECUTION_IMPLEMENTED:
                raise GatewayBlockedError("paper execution is disabled")
            return await self._broker.submit_order(order)
        # Any non-simulated broker is a live broker.
        if not (LIVE_EXECUTION_IMPLEMENTED and get_settings().live_execution_armed):
            raise GatewayBlockedError("live execution is disabled in this phase")
        return await self._broker.submit_order(order)
