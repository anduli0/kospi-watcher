"""Application service that turns a full agent run into a house prediction.

Runs all 21 agents (mock or LLM, via :class:`AgentService`), injects the BOK
monetary-policy stance into the MACRO desk (ADR-024), flattens the findings, and
hands them to the pure hierarchical synthesizer.
"""

from __future__ import annotations

from kospi_watcher.agent_service.accuracy_service import get_accuracy_service
from kospi_watcher.agent_service.service import AgentService
from kospi_watcher.agent_service.trend_service import get_trend_service
from kospi_watcher.config import get_settings
from kospi_watcher.domain.prediction.monetary_policy import (
    MonetaryPolicySignal,
    apply_to_findings,
    build_signal,
)
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.prediction.synthesizer import synthesize
from kospi_watcher.domain.prediction.trend_signal import apply_trend_to_findings


class PredictionService:
    def __init__(self, agents: AgentService | None = None) -> None:
        self._agents = agents or AgentService()

    def _policy_signal(
        self, news_headlines: list[str] | None
    ) -> MonetaryPolicySignal:
        settings = get_settings()
        return build_signal(
            stance_override=settings.monetary_policy_stance,
            hikes_override=settings.monetary_policy_hikes_2026,
            headlines=news_headlines or [],
        )

    async def generate(
        self,
        universe: tuple[str, ...] = (),
        *,
        news_headlines: list[str] | None = None,
    ) -> MarketPrediction:
        runs = await self._agents.run_all(universe)
        findings = [f for run in runs for f in run.findings]
        # Real price trend (primary anchor) + BOK monetary policy (risk tilt) +
        # the auto-feedback calibration learned from scoring past predictions.
        trend = await get_trend_service().latest()
        policy = self._policy_signal(news_headlines)
        calibration = await get_accuracy_service().calibration()
        findings = apply_trend_to_findings(findings, trend)
        findings = apply_to_findings(findings, policy)
        return synthesize(
            findings,
            generated_by=self._agents.runtime_name,
            agent_count=len(runs),
            news_headlines=news_headlines,
            monetary_policy=policy,
            trend_signal=trend,
            calibration=calibration,
        )
