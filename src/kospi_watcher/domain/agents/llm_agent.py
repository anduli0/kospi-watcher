"""Real, Anthropic-backed analysis agent.

``LLMAgent`` asks Claude (latest model by default) to produce one
:class:`AgentFinding` via a *forced* tool call — structured output guaranteed by
``tool_choice``. It has NO order-execution surface: like every agent it only
analyses. Server-controlled fields (agent name/version, timestamps, model,
schema version, evidence ``source_id``) are filled here, never by the model, so a
finding is always well-formed and scorable.

The Anthropic client is injected, so the agent is unit-testable offline with a
fake. ``build_async_anthropic_client`` lazily imports the SDK only when a real
client is actually constructed — importing this module never requires
``anthropic`` to be installed.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from kospi_watcher.domain.agents.base import AgentContext
from kospi_watcher.domain.agents.catalog import AgentSpec
from kospi_watcher.domain.agents.schemas import AgentFinding, Evidence
from kospi_watcher.domain.enums import (
    DataQuality,
    Horizon,
    Impact,
    MarketDirection,
    SourceType,
)

LLM_PROMPT_VERSION = "llm-2026.06"

_EMIT_TOOL_NAME = "emit_finding"

_DIRECTIONS = [d.value for d in MarketDirection]
_IMPACTS = [i.value for i in Impact]
_HORIZONS = [h.value for h in Horizon]
_DATA_QUALITY = [q.value for q in DataQuality]


class LLMAgentError(RuntimeError):
    """Raised when the model response cannot be turned into a finding."""


def _emit_tool() -> dict[str, Any]:
    return {
        "name": _EMIT_TOOL_NAME,
        "description": "Emit exactly one structured market-analysis finding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": _DIRECTIONS},
                "impact": {"type": "string", "enum": _IMPACTS},
                "horizon": {"type": "string", "enum": _HORIZONS},
                "confidence": {"type": "number"},
                "thesis": {"type": "string"},
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "claim": {"type": "string"},
                        },
                        "required": ["title", "claim"],
                    },
                },
                "counterevidence": {"type": "array", "items": {"type": "string"}},
                "affected_sectors": {"type": "array", "items": {"type": "string"}},
                "invalidation_conditions": {"type": "array", "items": {"type": "string"}},
                "data_quality": {"type": "string", "enum": _DATA_QUALITY},
            },
            "required": ["direction", "impact", "confidence", "thesis"],
        },
    }


class LLMAgent:
    """An Anthropic-backed implementation of the analysis-agent contract."""

    def __init__(
        self,
        spec: AgentSpec,
        *,
        client: Any,
        model: str,
        max_tokens: int = 2048,
        prompt_version: str = LLM_PROMPT_VERSION,
    ) -> None:
        self.spec = spec
        self.name = spec.name
        self.version = spec.version
        self.category = spec.category
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._prompt_version = prompt_version

    def _system(self) -> str:
        return (
            "You are a disciplined Korean equity (KOSPI) market-analysis agent. "
            f"Your role: {self.spec.summary} "
            "Produce exactly one finding by calling the emit_finding tool. Be "
            "calibrated: confidence in [0,1]. Every claim must be specific. You "
            "ONLY analyse — you have no authority to place orders."
        )

    def _user(self, ctx: AgentContext) -> str:
        universe = ", ".join(ctx.universe) if ctx.universe else "(broad market)"
        return (
            f"As-of (UTC): {ctx.as_of.isoformat()}\n"
            f"Instrument universe: {universe}\n"
            f"Category: {self.category}\n"
            "Emit one finding for the current Korean market with your directional "
            "view, impact, horizon, confidence, thesis, supporting evidence, and "
            "invalidation conditions."
        )

    async def generate(self, ctx: AgentContext) -> list[AgentFinding]:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system(),
                tools=[_emit_tool()],
                tool_choice={"type": "tool", "name": _EMIT_TOOL_NAME},
                messages=[{"role": "user", "content": self._user(ctx)}],
            )
        except Exception as exc:
            raise LLMAgentError(f"Anthropic request failed: {exc}") from exc

        block = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if block is None:
            raise LLMAgentError("model response contained no tool_use block")
        return [self._to_finding(ctx, dict(block.input))]

    def _to_finding(self, ctx: AgentContext, data: dict[str, Any]) -> AgentFinding:
        published = ctx.as_of - timedelta(hours=1)
        available = ctx.as_of - timedelta(minutes=30)
        raw_evidence = data.get("evidence") or [
            {"title": "model rationale", "claim": data.get("thesis", "")}
        ]
        evidence = [
            Evidence(
                source_id=f"LLM-{self._model}-{i}",
                source_type=SourceType.RESEARCH_NOTE,
                title=str(item.get("title", "model evidence")),
                url=None,
                published_at=published,
                available_at=available,
                claim=str(item.get("claim", "")),
            )
            for i, item in enumerate(raw_evidence)
        ]
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        return AgentFinding(
            agent_name=self.name,
            agent_version=self.version,
            as_of=ctx.as_of,
            horizon=_coerce(Horizon, data.get("horizon"), self.spec.horizon),
            direction=_coerce(MarketDirection, data.get("direction"), self.spec.direction),
            impact=_coerce(Impact, data.get("impact"), self.spec.impact),
            confidence=confidence,
            thesis=str(data.get("thesis", "")),
            evidence=evidence,
            counterevidence=[],
            affected_sectors=list(data.get("affected_sectors") or self.spec.sectors),
            affected_symbols=list(ctx.universe[:3]),
            invalidation_conditions=list(data.get("invalidation_conditions") or []),
            data_quality=_coerce(DataQuality, data.get("data_quality"), DataQuality.OK),
            model_name=self._model,
            prompt_version=self._prompt_version,
            created_at=ctx.as_of,
        )


def _coerce(enum_cls: Any, value: Any, default: Any) -> Any:
    """Best-effort enum coercion; fall back to the spec default on bad input."""
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError:
        return default


def build_async_anthropic_client(api_key: str) -> Any:
    """Construct an ``AsyncAnthropic`` client (SDK imported lazily)."""
    from anthropic import AsyncAnthropic

    return AsyncAnthropic(api_key=api_key)
