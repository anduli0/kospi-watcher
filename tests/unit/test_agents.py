"""The 21-agent registry, deterministic mock runtime, and finding schema."""

from __future__ import annotations

import pytest

from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.registry import (
    AgentNotFoundError,
    AgentRegistry,
    get_registry,
)
from kospi_watcher.domain.agents.schemas import (
    AGENT_FINDING_SCHEMA_VERSION,
    AgentFinding,
    AgentRunStatus,
)
from kospi_watcher.domain.time import now_utc


def test_registry_has_exactly_21_agents() -> None:
    assert len(get_registry()) == 21
    assert len(get_registry().names()) == 21


def test_run_one_agent_is_scorable_and_versioned() -> None:
    registry = AgentRegistry()
    run = registry.run("FX Agent", AgentContext(as_of=now_utc(), universe=("069500",)))
    assert run.status is AgentRunStatus.SUCCEEDED
    assert run.findings, "mock agent must emit at least one finding"
    finding = run.findings[0]
    assert finding.schema_version == AGENT_FINDING_SCHEMA_VERSION
    assert finding.is_scorable  # evidence carries a source_id
    assert finding.confidence == pytest.approx(finding.confidence)
    assert 0.0 <= finding.confidence <= 1.0


def test_unknown_agent_raises() -> None:
    with pytest.raises(AgentNotFoundError):
        AgentRegistry().run("No Such Agent", AgentContext(as_of=now_utc()))


def test_run_all_returns_21_succeeded() -> None:
    runs = AgentRegistry().run_all(AgentContext(as_of=now_utc()))
    assert len(runs) == 21
    assert all(r.status is AgentRunStatus.SUCCEEDED for r in runs)


def test_mock_runtime_is_deterministic() -> None:
    ctx = AgentContext(as_of=now_utc(), universe=("069500",))
    reg = AgentRegistry()
    a = reg.run("Korea Macro Agent", ctx).findings[0]
    b = reg.run("Korea Macro Agent", ctx).findings[0]
    assert a.confidence == b.confidence
    assert a.thesis == b.thesis


def test_agent_finding_json_schema_generates() -> None:
    schema = AgentFinding.model_json_schema()
    assert schema["type"] == "object"
    assert "confidence" in schema["properties"]
    assert "evidence" in schema["properties"]
