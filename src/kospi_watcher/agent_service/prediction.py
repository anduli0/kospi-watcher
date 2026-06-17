"""Application service that turns a full agent run into a house prediction.

Runs all 21 agents (mock or LLM, via :class:`AgentService`), flattens their
findings, and hands them to the pure hierarchical synthesizer.
"""

from __future__ import annotations

from kospi_watcher.agent_service.service import AgentService
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.prediction.synthesizer import synthesize


class PredictionService:
    def __init__(self, agents: AgentService | None = None) -> None:
        self._agents = agents or AgentService()

    async def generate(self, universe: tuple[str, ...] = ()) -> MarketPrediction:
        runs = await self._agents.run_all(universe)
        findings = [f for run in runs for f in run.findings]
        return synthesize(
            findings,
            generated_by=self._agents.runtime_name,
            agent_count=len(runs),
        )
