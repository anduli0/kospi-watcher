"""Deterministic Risk Engine domain (no LLM).

``deny-by-default``: an :class:`~kospi_watcher.domain.risk.schemas.OrderProposal`
is rejected unless every implemented, safety-critical check explicitly passes.
Only this layer produces a :class:`~kospi_watcher.domain.risk.schemas.RiskDecision`.
"""
