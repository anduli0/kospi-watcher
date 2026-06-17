"""The 13-state order machine: coverage, legal edges, illegal edges raise."""

from __future__ import annotations

import pytest

from kospi_watcher.domain.enums import OrderStatus
from kospi_watcher.domain.execution.order_state import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    IllegalTransitionError,
    OrderStateMachine,
    can_transition,
)


def test_machine_covers_all_thirteen_states() -> None:
    assert len(OrderStatus) == 13
    assert set(ALLOWED_TRANSITIONS) == set(OrderStatus)


def test_terminal_states_have_no_outgoing_edges() -> None:
    expected = {
        OrderStatus.RISK_REJECTED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.RECONCILIATION_ERROR,
    }
    assert TERMINAL_STATES == expected
    for state in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[state] == frozenset()


def test_happy_path_transitions_are_legal() -> None:
    sm = OrderStateMachine()  # starts PROPOSED
    sm.transition(OrderStatus.RISK_APPROVED)
    sm.transition(OrderStatus.APPROVED)
    sm.transition(OrderStatus.SUBMITTING)
    sm.transition(OrderStatus.SUBMITTED)
    sm.transition(OrderStatus.PARTIALLY_FILLED)
    sm.transition(OrderStatus.FILLED)
    assert sm.is_terminal
    assert sm.history[0] == OrderStatus.PROPOSED
    assert sm.history[-1] == OrderStatus.FILLED


def test_illegal_transition_raises() -> None:
    sm = OrderStateMachine()
    assert not can_transition(OrderStatus.PROPOSED, OrderStatus.FILLED)
    with pytest.raises(IllegalTransitionError):
        sm.transition(OrderStatus.FILLED)
    # A terminal state cannot move anywhere.
    sm2 = OrderStateMachine(OrderStatus.FILLED)
    with pytest.raises(IllegalTransitionError):
        sm2.transition(OrderStatus.CANCELLED)
