"""The 21-agent registry and mock-run orchestration."""

from __future__ import annotations

import uuid
from functools import lru_cache

from kospi_watcher.domain.agents.base import (
    MOCK_MODEL_NAME,
    MOCK_PROMPT_VERSION,
    AgentContext,
    MockAgent,
)
from kospi_watcher.domain.agents.catalog import AGENT_CATALOG, AgentSpec
from kospi_watcher.domain.agents.schemas import AgentRun, AgentRunStatus
from kospi_watcher.domain.time import now_utc


class AgentNotFoundError(KeyError):
    """Raised when an unknown agent name is requested."""


class AgentRegistry:
    def __init__(self, specs: tuple[AgentSpec, ...] = AGENT_CATALOG) -> None:
        self._agents: dict[str, MockAgent] = {s.name: MockAgent(s) for s in specs}

    def specs(self) -> list[AgentSpec]:
        return [agent.spec for agent in self._agents.values()]

    def names(self) -> list[str]:
        return list(self._agents.keys())

    def __len__(self) -> int:
        return len(self._agents)

    def get(self, name: str) -> MockAgent:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise AgentNotFoundError(name) from exc

    def run(self, name: str, ctx: AgentContext) -> AgentRun:
        """Run one agent and wrap the result in an AgentRun record."""
        agent = self.get(name)
        started = now_utc()
        try:
            findings = agent.run(ctx)
        except Exception as exc:
            return AgentRun(
                run_id=uuid.uuid4().hex,
                agent_name=agent.name,
                agent_version=agent.version,
                status=AgentRunStatus.FAILED,
                started_at=started,
                finished_at=now_utc(),
                model_name=MOCK_MODEL_NAME,
                prompt_version=MOCK_PROMPT_VERSION,
                error=str(exc),
            )
        return AgentRun(
            run_id=uuid.uuid4().hex,
            agent_name=agent.name,
            agent_version=agent.version,
            status=AgentRunStatus.SUCCEEDED,
            started_at=started,
            finished_at=now_utc(),
            model_name=MOCK_MODEL_NAME,
            prompt_version=MOCK_PROMPT_VERSION,
            findings=findings,
        )

    def run_all(self, ctx: AgentContext) -> list[AgentRun]:
        return [self.run(name, ctx) for name in self.names()]


@lru_cache
def get_registry() -> AgentRegistry:
    """Process-wide default registry built from the 21-agent catalog."""
    return AgentRegistry()
