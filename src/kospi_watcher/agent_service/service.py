"""Analysis-only service over the 21-agent registry.

Three runtimes: a deterministic ``mock`` (always available, offline), a real
``llm`` runtime backed by the Anthropic API, and a real ``claude_cli`` runtime
backed by the local Claude Code CLI on the user's Claude subscription. The
``llm`` runtime is used only when ``AGENT_RUNTIME=llm`` *and* an
``ANTHROPIC_API_KEY`` is present; ``claude_cli`` only when
``AGENT_RUNTIME=claude_cli`` *and* the CLI + setup-token are present. Any
failure falls back to the mock so the system always returns a well-formed
result. No runtime can place an order — agents only analyse.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from kospi_watcher.config import get_settings
from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.catalog import AgentSpec
from kospi_watcher.domain.agents.llm_agent import (
    LLM_PROMPT_VERSION,
    LLMAgent,
    LLMAgentError,
    build_async_anthropic_client,
)
from kospi_watcher.domain.agents.registry import AgentRegistry, get_registry
from kospi_watcher.domain.agents.schemas import AgentRun, AgentRunStatus
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.claude_cli import (
    build_claude_cli_client,
    resolve_cli_path,
    resolve_cli_token,
)
from kospi_watcher.logging_config import get_logger

log = get_logger("agent_service")


class AgentService:
    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry or get_registry()
        self._client: Any | None = None
        self._client_ready = False

    def list_specs(self) -> list[AgentSpec]:
        return self._registry.specs()

    def names(self) -> list[str]:
        return self._registry.names()

    @property
    def runtime_name(self) -> str:
        """The runtime that would actually be used (mock unless a real one is armed)."""
        settings = get_settings()
        if settings.agent_runtime == "llm" and settings.anthropic_api_key.get_secret_value():
            return "llm"
        if (
            settings.agent_runtime == "claude_cli"
            and resolve_cli_token()
            and resolve_cli_path(settings.claude_cli_path)
        ):
            return "claude_cli"
        return "mock"

    @property
    def model_name(self) -> str:
        """The model the active runtime would run ("mock" when offline)."""
        settings = get_settings()
        runtime = self.runtime_name
        if runtime == "llm":
            return settings.agent_model
        if runtime == "claude_cli":
            return settings.agent_cli_model
        return "mock"

    def _real_client(self, runtime: str) -> Any | None:
        """Lazily build the client for the armed real runtime (memoized)."""
        if not self._client_ready:
            self._client_ready = True
            settings = get_settings()
            if runtime == "llm":
                key = settings.anthropic_api_key.get_secret_value()
                if key:
                    self._client = build_async_anthropic_client(key)
            elif runtime == "claude_cli":
                self._client = build_claude_cli_client(
                    cli_path_override=settings.claude_cli_path,
                    timeout_seconds=float(settings.agent_cli_timeout_seconds),
                    concurrency=settings.agent_cli_concurrency,
                )
        return self._client

    def run_mock(self, agent_name: str, universe: tuple[str, ...] = ()) -> AgentRun:
        """Run a single mock agent. No real Anthropic call is made."""
        ctx = AgentContext(as_of=now_utc(), universe=universe)
        return self._registry.run(agent_name, ctx)

    async def run(self, agent_name: str, universe: tuple[str, ...] = ()) -> AgentRun:
        """Run a single agent using the configured runtime.

        Raises ``AgentNotFoundError`` for an unknown name; any LLM error degrades
        gracefully to the deterministic mock.
        """
        runtime = self.runtime_name
        if runtime == "mock":
            return self.run_mock(agent_name, universe)

        client = self._real_client(runtime)
        if client is None:
            return self.run_mock(agent_name, universe)

        model = self.model_name
        settings = get_settings()
        spec = self._registry.get(agent_name).spec  # raises AgentNotFoundError
        ctx = AgentContext(as_of=now_utc(), universe=universe)
        started = now_utc()
        try:
            findings = await LLMAgent(
                spec,
                client=client,
                model=model,
                max_tokens=settings.agent_max_tokens,
            ).generate(ctx)
        except LLMAgentError as exc:
            log.warning("agent_service.llm_fallback", agent=agent_name, error=str(exc))
            return self.run_mock(agent_name, universe)

        return AgentRun(
            run_id=uuid.uuid4().hex,
            agent_name=spec.name,
            agent_version=spec.version,
            status=AgentRunStatus.SUCCEEDED,
            started_at=started,
            finished_at=now_utc(),
            model_name=model,
            prompt_version=LLM_PROMPT_VERSION,
            findings=findings,
        )

    async def run_all(self, universe: tuple[str, ...] = ()) -> list[AgentRun]:
        """Run every agent with the configured runtime. LLM runs go concurrently;
        each agent still falls back to mock on its own failure."""
        return list(
            await asyncio.gather(*(self.run(name, universe) for name in self.names()))
        )
