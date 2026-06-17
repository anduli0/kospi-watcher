"""LLMAgent: maps a forced tool call into a valid AgentFinding (offline)."""

from __future__ import annotations

from typing import Any

import pytest

from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.catalog import AGENT_CATALOG
from kospi_watcher.domain.agents.llm_agent import LLMAgent, LLMAgentError
from kospi_watcher.domain.enums import Impact, MarketDirection
from kospi_watcher.domain.time import now_utc

_SPEC = AGENT_CATALOG[7]  # FX Agent (MACRO)


class _Block:
    type = "tool_use"

    def __init__(self, payload: dict[str, Any]) -> None:
        self.input = payload


class _Response:
    def __init__(self, content: list[Any]) -> None:
        self.content = content


class _Messages:
    def __init__(self, response: _Response | Exception) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _Client:
    def __init__(self, response: _Response | Exception) -> None:
        self.messages = _Messages(response)


async def test_llm_agent_builds_valid_finding() -> None:
    payload = {
        "direction": "BEARISH",
        "impact": "HIGH",
        "confidence": 0.72,
        "thesis": "원/달러 환율 급등으로 외국인 순매도 압력 확대.",
        "evidence": [{"title": "FX move", "claim": "USDKRW +1.5% intraday"}],
        "invalidation_conditions": ["환율이 1500 아래로 안정되면 무효화"],
    }
    client = _Client(_Response([_Block(payload)]))
    agent = LLMAgent(_SPEC, client=client, model="claude-opus-4-8")
    findings = await agent.generate(AgentContext(as_of=now_utc(), universe=("069500",)))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent_name == _SPEC.name
    assert finding.direction is MarketDirection.BEARISH
    assert finding.impact is Impact.HIGH
    assert finding.confidence == pytest.approx(0.72)
    assert finding.model_name == "claude-opus-4-8"
    assert finding.is_scorable  # synthesized source_id on evidence
    # The forced tool call was used.
    assert client.messages.calls[0]["tool_choice"]["name"] == "emit_finding"


async def test_llm_agent_clamps_and_defaults_bad_fields() -> None:
    payload = {
        "direction": "NONSENSE",  # invalid -> spec default
        "impact": "HIGH",
        "confidence": 5.0,  # out of range -> clamped to 1.0
        "thesis": "x",
    }
    agent = LLMAgent(_SPEC, client=_Client(_Response([_Block(payload)])), model="m")
    finding = (await agent.generate(AgentContext(as_of=now_utc())))[0]
    assert finding.direction is _SPEC.direction  # fell back to spec default
    assert finding.confidence == 1.0


async def test_llm_agent_raises_without_tool_use() -> None:
    agent = LLMAgent(_SPEC, client=_Client(_Response([])), model="m")
    with pytest.raises(LLMAgentError):
        await agent.generate(AgentContext(as_of=now_utc()))


async def test_llm_agent_wraps_client_errors() -> None:
    agent = LLMAgent(_SPEC, client=_Client(RuntimeError("boom")), model="m")
    with pytest.raises(LLMAgentError):
        await agent.generate(AgentContext(as_of=now_utc()))
