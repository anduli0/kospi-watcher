"""Execution domain — broker abstraction and the order state machine.

SECURITY BOUNDARY: ``submit_order`` is defined ONLY here (and called only by the
Execution Gateway). No analysis-agent module may import this package's order
path. The factory on ``ApprovedOrder`` refuses to construct without an APPROVED
``RiskDecision``.
"""
