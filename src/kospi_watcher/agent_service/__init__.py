"""Agent Service — runs analysis agents and validates their output.

ISOLATION: this package performs analysis only. It must never import the order
path (``kospi_watcher.domain.execution`` submit/broker). The security test
``tests/security/test_agent_no_submit_order.py`` enforces this statically.
"""
