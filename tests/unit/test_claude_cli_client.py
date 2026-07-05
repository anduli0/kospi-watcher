"""Claude Code CLI adapter — envelope parsing, prompt/env hygiene, LLMAgent fit."""

from __future__ import annotations

import json
from typing import Any

import pytest

from kospi_watcher.agent_service.service import AgentService
from kospi_watcher.config import get_settings
from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.llm_agent import LLMAgent, LLMAgentError
from kospi_watcher.domain.agents.registry import get_registry
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.claude_cli import (
    ClaudeCLIClient,
    ClaudeCLIError,
    _extract_json_object,
    _subprocess_env,
)

FINDING = {
    "direction": "BULLISH",
    "impact": "MEDIUM",
    "confidence": 0.62,
    "thesis": "외국인 순매수 지속",
}


def _envelope(result: str, *, subtype: str = "success", is_error: bool = False) -> str:
    return json.dumps({"subtype": subtype, "is_error": is_error, "result": result})


def _client(runner: Any) -> ClaudeCLIClient:
    return ClaudeCLIClient(cli_path="claude.exe", token="tok", runner=runner)


def _tools() -> list[dict[str, Any]]:
    return [{"name": "emit_finding", "input_schema": {"type": "object"}}]


async def _create(client: ClaudeCLIClient) -> Any:
    return await client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2048,
        system="you analyse",
        tools=_tools(),
        tool_choice={"type": "tool", "name": "emit_finding"},
        messages=[{"role": "user", "content": "emit one finding"}],
    )


# --- JSON extraction -----------------------------------------------------------


def test_extract_plain_object() -> None:
    assert _extract_json_object(json.dumps(FINDING)) == FINDING


def test_extract_fenced_object() -> None:
    text = "```json\n" + json.dumps(FINDING) + "\n```"
    assert _extract_json_object(text) == FINDING


def test_extract_object_with_prose() -> None:
    text = "Here is the finding:\n" + json.dumps(FINDING) + "\nDone."
    assert _extract_json_object(text) == FINDING


def test_extract_rejects_non_object() -> None:
    with pytest.raises(ClaudeCLIError):
        _extract_json_object("no json here")
    with pytest.raises(ClaudeCLIError):
        _extract_json_object("[1, 2]")


# --- messages.create over a fake runner ------------------------------------------


async def test_create_returns_tool_use_block() -> None:
    captured: dict[str, Any] = {}

    def runner(cmd: list[str], prompt: str, env: dict[str, str], timeout: float) -> str:
        captured.update(cmd=cmd, prompt=prompt, env=env, timeout=timeout)
        return _envelope(json.dumps(FINDING))

    response = await _create(_client(runner))
    block = response.content[0]
    assert block.type == "tool_use"
    assert block.name == "emit_finding"
    assert dict(block.input) == FINDING
    # Prompt carries the user message + the tool schema; CLI gets no tools.
    assert "emit one finding" in captured["prompt"]
    assert '"type": "object"' in captured["prompt"]
    assert "--tools" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--model") + 1] == "claude-sonnet-5"


async def test_subprocess_env_is_scrubbed_and_token_injected(monkeypatch: Any) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-dead-credits")
    env = _subprocess_env("tok-123")
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-123"
    assert "CLAUDECODE" not in env
    assert "CLAUDE_CODE_ENTRYPOINT" not in env
    assert "ANTHROPIC_API_KEY" not in env


async def test_error_envelope_raises() -> None:
    def runner(cmd: list[str], prompt: str, env: dict[str, str], timeout: float) -> str:
        return _envelope("limit reached", subtype="error_during_execution", is_error=True)

    with pytest.raises(ClaudeCLIError):
        await _create(_client(runner))


async def test_non_json_stdout_raises() -> None:
    def runner(cmd: list[str], prompt: str, env: dict[str, str], timeout: float) -> str:
        return "Failed to authenticate."

    with pytest.raises(ClaudeCLIError):
        await _create(_client(runner))


# --- LLMAgent compatibility (the adapter is a drop-in client) --------------------


async def test_llm_agent_generates_finding_over_cli_client() -> None:
    def runner(cmd: list[str], prompt: str, env: dict[str, str], timeout: float) -> str:
        return _envelope(json.dumps(FINDING))

    spec = get_registry().specs()[0]
    agent = LLMAgent(spec, client=_client(runner), model="claude-sonnet-5")
    findings = await agent.generate(AgentContext(as_of=now_utc(), universe=("069500",)))
    assert len(findings) == 1
    assert findings[0].direction.value == "BULLISH"
    assert findings[0].confidence == pytest.approx(0.62)
    assert findings[0].model_name == "claude-sonnet-5"


async def test_llm_agent_wraps_cli_error() -> None:
    def runner(cmd: list[str], prompt: str, env: dict[str, str], timeout: float) -> str:
        raise ClaudeCLIError("boom")

    spec = get_registry().specs()[0]
    agent = LLMAgent(spec, client=_client(runner), model="claude-sonnet-5")
    with pytest.raises(LLMAgentError):
        await agent.generate(AgentContext(as_of=now_utc(), universe=()))


# --- Runtime selection ------------------------------------------------------------


def test_runtime_stays_mock_without_cli_arming(monkeypatch: Any) -> None:
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    assert AgentService().runtime_name == "mock"


def test_runtime_claude_cli_when_armed(monkeypatch: Any, tmp_path: Any) -> None:
    fake_cli = tmp_path / "claude.exe"
    fake_cli.write_text("stub")
    monkeypatch.setenv("AGENT_RUNTIME", "claude_cli")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    monkeypatch.setenv("CLAUDE_CLI_PATH", str(fake_cli))
    get_settings.cache_clear()
    try:
        service = AgentService()
        assert service.runtime_name == "claude_cli"
        assert service.model_name == get_settings().agent_cli_model
    finally:
        get_settings.cache_clear()
