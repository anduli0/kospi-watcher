"""Claude Code CLI (subscription) client — an AsyncAnthropic-shaped adapter.

Lets the 21 analysis agents run on the user's Claude subscription instead of
API credits: each ``messages.create(...)`` call is served by one headless run of
the local ``claude`` CLI in print mode (``-p``), authenticated by the long-lived
token minted once with ``claude setup-token`` (read from the
``CLAUDE_CODE_OAUTH_TOKEN`` env var, or ``~/.claude/oauth-token.secret``).

The adapter mirrors the Anthropic SDK's response just enough for
:class:`~kospi_watcher.domain.agents.llm_agent.LLMAgent`: a ``content`` list with
one ``tool_use`` block whose ``input`` is the model's JSON finding. The forced
tool call is emulated by instructing the model to answer with ONLY a JSON object
matching the tool's input schema.

Safety properties (mirrors ADR-015):
- Analysis-only. The CLI is launched with ``--tools ""`` (no tool surface) and
  ``--no-session-persistence``; it can only produce text.
- Any failure (missing CLI/token, timeout, non-JSON output) raises, so the
  caller's per-agent mock fallback engages and a run always completes.
- The token is never logged; subprocess env strips all inherited CLAUDE_*/
  ANTHROPIC_* variables before injecting the subscription token.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kospi_watcher.logging_config import get_logger

log = get_logger("claude_cli")

_TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"  # noqa: S105 — env var *name*, not a secret
_TOKEN_FILE = Path.home() / ".claude" / "oauth-token.secret"

# Windows: don't flash a console window per agent call.
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class ClaudeCLIError(RuntimeError):
    """Raised when the CLI run fails or its output cannot be parsed."""


def resolve_cli_token() -> str | None:
    """The subscription token: env var first, then the setup-token file."""
    token = os.environ.get(_TOKEN_ENV, "").strip()
    if token:
        return token
    try:
        token = _TOKEN_FILE.read_text(encoding="ascii").strip()
    except OSError:
        return None
    return token or None


def resolve_cli_path(override: str = "") -> str | None:
    """Locate the ``claude`` executable (explicit override > known homes > PATH)."""
    candidates: list[str] = []
    if override:
        candidates.append(override)
    candidates.append(str(Path.home() / ".local" / "bin" / "claude.exe"))
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.append(str(Path(appdata) / "npm" / "claude.cmd"))
    for cand in candidates:
        if Path(cand).is_file():
            return cand
    return shutil.which("claude")


def _subprocess_env(token: str) -> dict[str, str]:
    """Inherited env minus every Claude/Anthropic variable, plus the token.

    A parent Claude Code session exports CLAUDE_CODE_* markers that make a child
    CLI defer auth to a host that isn't there; a stale ANTHROPIC_API_KEY would
    silently bill dead credits instead of the subscription. Strip both.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CLAUDE_CODE_", "ANTHROPIC_", "CLAUDE_"))
        and k != "CLAUDECODE"
    }
    env[_TOKEN_ENV] = token
    return env


def _run_cli(cmd: list[str], prompt: str, env: dict[str, str], timeout: float) -> str:
    """Blocking CLI invocation (prompt via stdin); returns raw stdout."""
    # S603: cmd is a fixed flag list around a locally-resolved executable; the
    # only variable parts are the model name (config) and stdin, never shell.
    proc = subprocess.run(  # noqa: S603
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-400:]
        raise ClaudeCLIError(f"claude CLI exited {proc.returncode}: {tail}")
    return proc.stdout


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse the model's answer as one JSON object (tolerating code fences)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```", 2)[1]
        stripped = stripped.removeprefix("json").strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        raise ClaudeCLIError(f"no JSON object in CLI answer: {stripped[:200]!r}")
    try:
        data = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ClaudeCLIError(f"invalid JSON in CLI answer: {exc}") from exc
    if not isinstance(data, dict):
        raise ClaudeCLIError("CLI answer is JSON but not an object")
    return data


@dataclass
class CLIToolUseBlock:
    """Just enough of the SDK's ToolUseBlock for LLMAgent."""

    input: dict[str, Any]
    name: str
    type: str = "tool_use"


@dataclass
class CLIMessage:
    content: list[CLIToolUseBlock] = field(default_factory=list)


class ClaudeCLIClient:
    """AsyncAnthropic-shaped client backed by headless ``claude -p`` runs."""

    def __init__(
        self,
        *,
        cli_path: str,
        token: str,
        timeout_seconds: float = 240.0,
        concurrency: int = 3,
        runner: Callable[[list[str], str, dict[str, str], float], str] | None = None,
    ) -> None:
        self._cli_path = cli_path
        self._token = token
        self._timeout = timeout_seconds
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._runner = runner or _run_cli
        self.messages = _Messages(self)

    def _invoke(self, *, model: str, system: str, prompt: str) -> str:
        cmd = [
            self._cli_path,
            "-p",
            "--model",
            model,
            "--output-format",
            "json",
            "--tools",
            "",
            "--no-session-persistence",
            "--system-prompt",
            system,
        ]
        return self._runner(cmd, prompt, _subprocess_env(self._token), self._timeout)


class _Messages:
    def __init__(self, client: ClaudeCLIClient) -> None:
        self._client = client

    async def create(
        self,
        *,
        model: str,
        system: str,
        tools: list[dict[str, Any]],
        tool_choice: dict[str, Any],
        messages: list[dict[str, Any]],
        max_tokens: int = 2048,
    ) -> CLIMessage:
        del max_tokens  # print mode has no per-call cap; schema keeps output small
        tool_name = str(tool_choice.get("name") or (tools[0]["name"] if tools else "emit"))
        schema = tools[0].get("input_schema", {}) if tools else {}
        user = str(messages[-1]["content"]) if messages else ""
        prompt = (
            f"{user}\n\n"
            f"Answer by emitting exactly one `{tool_name}` result: a single JSON "
            "object that validates against this JSON Schema:\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n\n"
            "Output ONLY the JSON object — no prose, no code fences, no tool use."
        )
        async with self._client._semaphore:
            stdout = await asyncio.to_thread(
                self._client._invoke, model=model, system=system, prompt=prompt
            )
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeCLIError(f"CLI printed non-JSON envelope: {exc}") from exc
        if envelope.get("is_error") or envelope.get("subtype") != "success":
            raise ClaudeCLIError(
                f"CLI run failed: subtype={envelope.get('subtype')!r} "
                f"result={str(envelope.get('result'))[:200]!r}"
            )
        data = _extract_json_object(str(envelope.get("result", "")))
        return CLIMessage(content=[CLIToolUseBlock(input=data, name=tool_name)])


def build_claude_cli_client(
    *,
    cli_path_override: str = "",
    timeout_seconds: float = 240.0,
    concurrency: int = 3,
) -> ClaudeCLIClient | None:
    """Build the CLI client, or ``None`` when the CLI or token is missing."""
    token = resolve_cli_token()
    cli_path = resolve_cli_path(cli_path_override)
    if not token or not cli_path:
        return None
    return ClaudeCLIClient(
        cli_path=cli_path,
        token=token,
        timeout_seconds=timeout_seconds,
        concurrency=concurrency,
    )
