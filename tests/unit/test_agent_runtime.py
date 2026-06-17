"""AgentService runtime selection and graceful mock fallback."""

from __future__ import annotations

from kospi_watcher.agent_service.service import AgentService
from kospi_watcher.domain.agents.schemas import AgentRunStatus


def test_default_runtime_is_mock_without_key() -> None:
    # Test env sets no ANTHROPIC_API_KEY and AGENT_RUNTIME defaults to "mock".
    assert AgentService().runtime_name == "mock"


async def test_run_uses_mock_when_not_armed() -> None:
    run = await AgentService().run("FX Agent", ("069500",))
    assert run.status is AgentRunStatus.SUCCEEDED
    assert run.agent_name == "FX Agent"
    assert run.model_name == "mock-deterministic-v0"  # the mock runtime
    assert run.findings
