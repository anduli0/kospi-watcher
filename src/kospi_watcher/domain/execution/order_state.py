"""Order state machine over the 13 :class:`OrderStatus` values.

Only the transitions in ``ALLOWED_TRANSITIONS`` are legal; any other transition
raises :class:`IllegalTransitionError`. Terminal states allow no outgoing edges.
"""

from __future__ import annotations

from kospi_watcher.domain.enums import OrderStatus

S = OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    S.PROPOSED: frozenset({S.RISK_REJECTED, S.RISK_APPROVED}),
    S.RISK_REJECTED: frozenset(),
    S.RISK_APPROVED: frozenset({S.AWAITING_HUMAN, S.APPROVED, S.REJECTED}),
    S.AWAITING_HUMAN: frozenset({S.APPROVED, S.REJECTED, S.CANCELLED}),
    S.APPROVED: frozenset({S.SUBMITTING, S.CANCELLED}),
    S.SUBMITTING: frozenset({S.SUBMITTED, S.REJECTED}),
    S.SUBMITTED: frozenset(
        {S.PARTIALLY_FILLED, S.FILLED, S.CANCEL_PENDING, S.REJECTED, S.RECONCILIATION_ERROR}
    ),
    S.PARTIALLY_FILLED: frozenset(
        {S.PARTIALLY_FILLED, S.FILLED, S.CANCEL_PENDING, S.RECONCILIATION_ERROR}
    ),
    S.CANCEL_PENDING: frozenset({S.CANCELLED, S.FILLED, S.RECONCILIATION_ERROR}),
    S.FILLED: frozenset(),
    S.CANCELLED: frozenset(),
    S.REJECTED: frozenset(),
    S.RECONCILIATION_ERROR: frozenset(),
}

TERMINAL_STATES: frozenset[OrderStatus] = frozenset(
    state for state, nexts in ALLOWED_TRANSITIONS.items() if not nexts
)

# Every status must be represented exactly once.
assert set(ALLOWED_TRANSITIONS) == set(OrderStatus), (  # noqa: S101
    "state machine must cover all 13 states"
)


class IllegalTransitionError(RuntimeError):
    """Raised on an attempt to perform a transition not in ALLOWED_TRANSITIONS."""

    def __init__(self, src: OrderStatus, dst: OrderStatus) -> None:
        super().__init__(f"illegal order transition: {src} -> {dst}")
        self.src = src
        self.dst = dst


def can_transition(src: OrderStatus, dst: OrderStatus) -> bool:
    return dst in ALLOWED_TRANSITIONS[src]


def assert_transition(src: OrderStatus, dst: OrderStatus) -> None:
    if not can_transition(src, dst):
        raise IllegalTransitionError(src, dst)


class OrderStateMachine:
    """A tiny helper tracking an order's status and transition history."""

    def __init__(self, status: OrderStatus = OrderStatus.PROPOSED) -> None:
        self.status = status
        self.history: list[OrderStatus] = [status]

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    def transition(self, to: OrderStatus) -> OrderStatus:
        assert_transition(self.status, to)
        self.status = to
        self.history.append(to)
        return self.status
