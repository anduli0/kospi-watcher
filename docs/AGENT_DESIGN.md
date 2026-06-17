# KOSPI-WATCHER — Agent Design (21-Agent Analysis Layer)

This document describes the analysis layer of KOSPI-WATCHER: a fixed catalog of
**21 agents** that read market context and emit a single versioned finding
contract. It is written to match the code exactly. The source of truth is:

- `src/kospi_watcher/domain/agents/catalog.py` — the 21 `AgentSpec` entries.
- `src/kospi_watcher/domain/agents/base.py` — `AgentContext`, the `AnalysisAgent`
  protocol, and the deterministic `MockAgent`.
- `src/kospi_watcher/domain/agents/llm_agent.py` — `LLMAgent`, the real
  Anthropic-backed implementation (forced `emit_finding` tool).
- `src/kospi_watcher/domain/agents/registry.py` — `AgentRegistry` / run orchestration.
- `src/kospi_watcher/domain/agents/schemas.py` — `Evidence`, `AgentFinding`, `AgentRun`.
- `src/kospi_watcher/agent_service/service.py` and `app.py` — the isolated service
  (`run_mock` + the runtime-aware async `run`).
- `src/kospi_watcher/domain/enums.py` — the enum value sets.

---

## 1. Design principles

**Agents are ANALYSIS ONLY.** The `AnalysisAgent` protocol in `base.py` deliberately
exposes **no order-execution surface**. Its entire structural contract is:

```python
@runtime_checkable
class AnalysisAgent(Protocol):
    """Structural type every agent satisfies. Note: no order-execution surface."""
    name: str
    version: str
    category: str
    def run(self, ctx: AgentContext) -> list[AgentFinding]: ...
```

There is no `submit`, no `order`, no broker handle — an agent can only return a list
of `AgentFinding`. Order authority lives elsewhere (the deterministic Risk Engine);
agents never touch it. The standalone agent-service's `/health` endpoint states this
inline: `"note": "analysis only; no order authority"`.

**One versioned contract.** Every agent emits the single, schema-versioned
`AgentFinding`. Its `schema_version` defaults to the constant
`AGENT_FINDING_SCHEMA_VERSION`, whose current value is **`"1.0.0"`**
(`schemas.py`). The comment on that constant is explicit: *"Bump on any breaking
change to AgentFinding / Evidence shape."*

**Scorability requires a source.** A finding is scorable only if at least one of its
`Evidence` items carries a non-empty `source_id`. This is enforced both by the schema
(`Evidence.source_id` has `min_length=1` and is required) and by the
`AgentFinding.is_scorable` property:

```python
@property
def is_scorable(self) -> bool:
    """Scorable only if at least one evidence item carries a source_id."""
    return any(e.source_id for e in self.evidence)
```

A claim with no source is excluded from scoring.

**Point-in-time discipline.** All timestamps are timezone-aware. `Evidence.published_at`
and `Evidence.available_at`, plus `AgentFinding.as_of` / `created_at`, are Pydantic
`AwareDatetime` fields that reject naive datetimes. `AgentContext.__post_init__` calls
`ensure_aware(self.as_of)`, so a run cannot start from a naive timestamp. This keeps
"what was knowable when" honest and prevents lookahead leakage.

**Two runtimes; mock is the default.** Agents run on one of two interchangeable
runtimes (see §6 for the full contract): a deterministic `mock` (the default) and a
real Anthropic-backed `llm`. The `mock` `MockAgent` performs **no** real Anthropic call
and is fully reproducible from `(name, as_of)`: the seed is
`int(sha256(f"{name}|{as_of.isoformat()}")[:8], 16)`, and confidence, evidence id, and
timestamps derive from that seed. Every field is flagged as MOCK so it can never be
mistaken for real market data — the evidence title is `"MOCK DATA — NOT REAL MARKET
DATA"`, the thesis is prefixed `[MOCK]`, the source id is `MOCK-<seed>`, and
`model_name` / `prompt_version` are the mock constants
`MOCK_MODEL_NAME = "mock-deterministic-v0"` and `MOCK_PROMPT_VERSION = "mock-2026.06"`.
The `llm` runtime is used only when armed and **falls back to the mock** on any error,
so a well-formed result is always returned. **Neither runtime can place an order.**

---

## 2. The 21 agents

The catalog (`AGENT_CATALOG` in `catalog.py`) is the **canonical list**. All agents
currently share `AGENT_VERSION = "0.1.0"`. They are listed below in catalog order.
Summaries are reproduced verbatim in Korean.

| #  | Agent Name | Category | Horizon | Default Direction | Impact | Summary |
|----|------------|----------|---------|-------------------|--------|---------|
| 1  | Market Data Integrity Agent | DATA_INTEGRITY | INTRADAY | NEUTRAL | MEDIUM | 시세·수급·지표 데이터의 결측/지연/이상치 무결성 점검 |
| 2  | News Deduplication Agent | NEWS | INTRADAY | NEUTRAL | LOW | 동일 사건 뉴스 군집화 및 중복 제거 |
| 3  | Source Verification Agent | NEWS | INTRADAY | NEUTRAL | MEDIUM | 출처 신뢰도 검증 및 미검증 주장 격리 |
| 4  | Disclosure and Corporate Event Agent | DISCLOSURE | D1 | NEUTRAL | MEDIUM | DART 공시·기업 이벤트 영향 분석 |
| 5  | Korea Macro Agent | MACRO | D20 | BULLISH | MEDIUM | 한국 성장·물가·고용·수출·한국은행 정책 분석 |
| 6  | Global Growth Agent | MACRO | D20 | BULLISH | MEDIUM | 미국·중국 등 글로벌 경기와 위험선호 분석 |
| 7  | Rates and Liquidity Agent | MACRO | D20 | BEARISH | HIGH | 연준·금리·글로벌 유동성 흐름 분석 |
| 8  | FX Agent | MACRO | D5 | BEARISH | MEDIUM | 원/달러 환율과 수출주·외국인 수급 민감도 분석 |
| 9  | Commodity and Energy Agent | MACRO | D5 | NEUTRAL | MEDIUM | 유가·원자재·에너지 가격이 섹터에 미치는 영향 분석 |
| 10 | Geopolitics and Trade Agent | GEOPOLITICS | D5 | BEARISH | HIGH | 국제정세·무역분쟁·제재·공급망 리스크 분석 |
| 11 | Foreign and Institutional Flow Agent | FLOW | D1 | BULLISH | HIGH | 외국인·기관·개인 투자자별 수급 분석 |
| 12 | Derivatives and Program Agent | FLOW | INTRADAY | NEUTRAL | MEDIUM | 프로그램 매매·선물 베이시스·옵션 포지션 분석 |
| 13 | Breadth and Technical Agent | TECHNICAL | D5 | BULLISH | MEDIUM | 시장 폭·추세·모멘텀·신고저가 기술적 분석 |
| 14 | Volatility and Regime Agent | REGIME | D1 | NEUTRAL | HIGH | 변동성 국면과 9개 레짐 분류 신호 산출 |
| 15 | Earnings and Valuation Agent | FUNDAMENTAL | D20 | BULLISH | MEDIUM | 이익 추정치 변화와 밸류에이션 분석 |
| 16 | Technology and Semiconductor Agent | SECTOR | D20 | BULLISH | HIGH | 반도체·IT 사이클과 수출 모멘텀 분석 |
| 17 | Industrial and Export Agent | SECTOR | D20 | BULLISH | MEDIUM | 조선·기계·자동차 등 수출 제조업 분석 |
| 18 | Domestic Demand and Defensive Agent | SECTOR | D20 | NEUTRAL | LOW | 내수·필수소비재·통신·유틸리티 방어주 분석 |
| 19 | Structural Growth Scout | STRUCTURAL | STRUCTURAL | BULLISH | HIGH | AI·전력·원전·방산·로봇 등 장기 성장 산업 탐색 |
| 20 | Red-Team and Risk Agent | RISK | D5 | BEARISH | HIGH | 낙관 시나리오 반증·꼬리위험·투자논거 무효화 조건 점검 |
| 21 | Chief Market Synthesizer | SYNTHESIS | D5 | NEUTRAL | HIGH | 전 에이전트 결과 종합 및 시장 국면·전망 합성 |

Four agents carry default `sectors`:

- **Technology and Semiconductor Agent** — `반도체, IT하드웨어, 소프트웨어`
- **Industrial and Export Agent** — `조선, 기계, 자동차`
- **Domestic Demand and Defensive Agent** — `필수소비재, 통신, 유틸리티`
- **Structural Growth Scout** — `AI, 전력기기, 원전, 방산, 로봇`

The catalog ends with a hard invariant:

```python
assert len(AGENT_CATALOG) == 21, "the agent catalog must contain exactly 21 agents"
```

The final agent, **Chief Market Synthesizer** (category `SYNTHESIS`), is the composer:
it synthesizes the output of the other agents into a market regime / outlook view.

---

## 3. The AgentFinding contract

### `Evidence`

A single sourced claim backing (or opposing) a finding. `model_config` is
`extra="forbid"`, so unknown fields are rejected.

| Field | Type | Meaning |
|-------|------|---------|
| `source_id` | `str` (`min_length=1`, required) | Stable source identifier. Required and non-empty — claims without a `source_id` are excluded from scoring. |
| `source_type` | `SourceType` | Kind of source (see §4). |
| `title` | `str` | Human-readable title of the source. |
| `url` | `str \| None` (default `None`) | Optional link to the source. |
| `published_at` | `AwareDatetime` | When the source was published (timezone-aware). |
| `available_at` | `AwareDatetime` | When the source first became available to the system (timezone-aware). |
| `claim` | `str` | The specific claim this evidence supports or opposes. |

### `AgentFinding`

The versioned output contract for every analysis agent. `model_config` is
`extra="forbid"`.

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | `str` (default `AGENT_FINDING_SCHEMA_VERSION` = `"1.0.0"`) | Finding-contract version; bumped on any breaking shape change. |
| `agent_name` | `str` | Name of the emitting agent (matches a catalog entry). |
| `agent_version` | `str` | Version of the agent (currently `"0.1.0"`). |
| `as_of` | `AwareDatetime` | Point-in-time the analysis is anchored to. |
| `horizon` | `Horizon` | Forecast horizon for the view. |
| `direction` | `MarketDirection` | Directional market view (BULLISH / BEARISH / NEUTRAL) — **not** an order side. |
| `impact` | `Impact` | How market-moving the finding is, independent of confidence. |
| `confidence` | `float` (`ge=0.0, le=1.0`) | Confidence in `[0, 1]`. |
| `thesis` | `str` | The core argument of the finding. |
| `evidence` | `list[Evidence]` (default `[]`) | Supporting sourced claims. |
| `counterevidence` | `list[Evidence]` (default `[]`) | Opposing sourced claims. |
| `affected_sectors` | `list[str]` (default `[]`) | Sectors the finding bears on. |
| `affected_symbols` | `list[str]` (default `[]`) | Symbols the finding bears on. |
| `invalidation_conditions` | `list[str]` (default `[]`) | Conditions that would invalidate the thesis. |
| `data_quality` | `DataQuality` | Quality flag for the inputs behind the finding. |
| `model_name` | `str` | Name of the model that produced it (mock: `mock-deterministic-v0`). |
| `prompt_version` | `str` | Prompt version (mock: `mock-2026.06`). |
| `created_at` | `AwareDatetime` | When the finding record was created. |

**`is_scorable`** is a derived property, not a stored field:
`return any(e.source_id for e in self.evidence)`. Because every `Evidence.source_id`
is required and non-empty, a finding is scorable iff it carries at least one evidence
item. Findings with empty `evidence` are excluded from scoring.

---

## 4. Categories & source types

### Categories present in the catalog

The 21 agents span these categories (exact strings from `catalog.py`):

`DATA_INTEGRITY`, `NEWS`, `DISCLOSURE`, `MACRO`, `GEOPOLITICS`, `FLOW`,
`TECHNICAL`, `REGIME`, `FUNDAMENTAL`, `SECTOR`, `STRUCTURAL`, `RISK`, `SYNTHESIS`.

### `_CATEGORY_SOURCE` mapping (`base.py`)

The mock runtime picks an evidence `SourceType` per category via `_CATEGORY_SOURCE`
(falling back to `SourceType.OTHER` for any unmapped category):

| Category | SourceType emitted |
|----------|--------------------|
| `DATA_INTEGRITY` | `PRICE_DATA` |
| `NEWS` | `NEWS` |
| `DISCLOSURE` | `DISCLOSURE` |
| `MACRO` | `MACRO_RELEASE` |
| `GEOPOLITICS` | `NEWS` |
| `FLOW` | `FLOW_DATA` |
| `TECHNICAL` | `PRICE_DATA` |
| `REGIME` | `PRICE_DATA` |
| `FUNDAMENTAL` | `RESEARCH_NOTE` |
| `SECTOR` | `RESEARCH_NOTE` |
| `STRUCTURAL` | `RESEARCH_NOTE` |
| `RISK` | `OTHER` |
| `SYNTHESIS` | `OTHER` |

### Enum value sets (`enums.py`)

- **`Horizon`**: `INTRADAY`, `D1`, `D5`, `D20`, `STRUCTURAL`.
- **`MarketDirection`**: `BULLISH`, `BEARISH`, `NEUTRAL` — a market view, not an order side.
- **`Impact`**: `LOW`, `MEDIUM`, `HIGH` — market-moving magnitude, independent of confidence.
- **`DataQuality`**: `OK`, `PARTIAL`, `STALE`, `UNAVAILABLE`.
- **`SourceType`**: `NEWS`, `DISCLOSURE`, `MACRO_RELEASE`, `PRICE_DATA`, `FLOW_DATA`,
  `RESEARCH_NOTE`, `REGULATORY`, `OTHER`.

Every enum is a `StrEnum`; the **string value** (not the integer position) is the
stable wire/storage representation.

---

## 5. Runtime & registry

### `AgentRegistry` (`registry.py`)

`AgentRegistry` is built from `AGENT_CATALOG` by default, wrapping each `AgentSpec`
in a `MockAgent` keyed by name. It exposes `specs()`, `names()`, `__len__`, and
`get(name)` (raising `AgentNotFoundError`, a `KeyError` subclass, for unknown names).
`get_registry()` is `@lru_cache`-d, so there is one process-wide default registry.

**Running one agent** — `run(name, ctx)`:

1. `get(name)` resolves the agent (or raises `AgentNotFoundError`).
2. `started = now_utc()`.
3. `agent.run(ctx)` is invoked inside a `try`. **Failures are captured, not raised:**
   any exception yields an `AgentRun` with `status = AgentRunStatus.FAILED`, a
   `finished_at`, the mock model/prompt metadata, and `error = str(exc)`.
4. On success, returns an `AgentRun` with `status = AgentRunStatus.SUCCEEDED` and the
   `findings` list.

Each `AgentRun` carries a fresh `run_id = uuid.uuid4().hex`, `agent_name`,
`agent_version`, `status`, `started_at`, `finished_at`, `model_name`,
`prompt_version`, `findings`, and `error`. `AgentRunStatus` values are `PENDING`,
`RUNNING`, `SUCCEEDED`, `FAILED`.

**Running all agents** — `run_all(ctx)` returns one `AgentRun` per name in registry
order, i.e. **21 runs** for the default catalog.

### `AgentService` (`agent_service/service.py`)

`AgentService` wraps a registry (defaulting to `get_registry()`) and offers:

- `list_specs()` → the 21 `AgentSpec`s.
- `names()` → the agent names.
- `runtime_name` (property) → the runtime that would actually be used: `"llm"` only
  when `agent_runtime == "llm"` **and** an `ANTHROPIC_API_KEY` is present, else `"mock"`.
- `run_mock(agent_name, universe=())` → builds an `AgentContext(as_of=now_utc(),
  universe=universe)` and delegates to `registry.run(...)`. No real Anthropic call is
  made.
- `run(agent_name, universe=())` (async) → runs the **configured** runtime. If
  `runtime_name != "llm"` (or the client cannot be built), it delegates to `run_mock`.
  Otherwise it builds an `LLMAgent` from the resolved `AgentSpec` and the configured
  `agent_model` / `agent_max_tokens`, and **falls back to `run_mock` on any
  `LLMAgentError`** (logged as `agent_service.llm_fallback`). Unknown names still raise
  `AgentNotFoundError`.

### Isolated agent-service (`agent_service/app.py`)

A standalone FastAPI app (`title="KOSPI-WATCHER agent-service"`, `version="0.1.0"`),
deliberately separate from the main API to demonstrate isolation from the Execution
Gateway. It has no order-execution surface. Endpoints:

- **`GET /health`** → `{"status": "ok", "service": "agent-service",
  "agent_count": <n>, "note": "analysis only; no order authority"}`.
- **`GET /agents`** → `AgentListResponse` with `count` and one `AgentInfo`
  (`name`, `version`, `category`, `summary`, `enabled=True`) per spec.
- **`POST /run`** → takes a `MockRunRequest` (`agent_name`, `universe`), returns the
  `AgentRun`. Unknown agent names map `AgentNotFoundError` → HTTP `404`
  (`"unknown agent: <name>"`).

---

## 6. Runtimes (deterministic mock vs Anthropic LLM)

The catalog is the **stable contract**. Agent **names, versions, and categories** in
`catalog.py` are what the rest of the system depends on; they do not change with the
runtime. Two interchangeable runtimes implement the same `AnalysisAgent` surface and the
same `AgentFinding` contract:

### 6.1 `mock` (default)

The deterministic `MockAgent` (§1, §5). Always available, fully offline, fully
reproducible. Every field is flagged MOCK; `model_name` / `prompt_version` are the mock
constants. This is the default (`AGENT_RUNTIME` unset → `agent_runtime="mock"`).

### 6.2 `llm` — `LLMAgent` (`domain/agents/llm_agent.py`)

A real, Anthropic-backed implementation of the analysis-agent contract.

- **Forced structured output.** `generate(ctx)` calls
  `client.messages.create(...)` with a single `emit_finding` tool and
  `tool_choice={"type": "tool", "name": "emit_finding"}`, so the model **must** return
  exactly one structured finding (no free-text path). The tool's `input_schema`
  constrains `direction` / `impact` / `horizon` / `data_quality` to the enum value sets
  (§4) and requires `direction`, `impact`, `confidence`, `thesis`. The first `tool_use`
  block is parsed into an `AgentFinding`; a response with no `tool_use` block raises
  `LLMAgentError`.
- **Server fills the trusted fields.** Agent name/version, `as_of` / `created_at`,
  `model_name`, `schema_version`, and each evidence `source_id` (`LLM-<model>-<i>`) are
  set **in code, never by the model**, so a finding is always well-formed and scorable.
  `confidence` is clamped to `[0, 1]`; enum fields fall back to the spec defaults on bad
  input (`_coerce`). `prompt_version` is `LLM_PROMPT_VERSION = "llm-2026.06"`.
- **Injected client → testable offline.** The Anthropic client is injected into
  `LLMAgent`, so it can be unit-tested with a fake. `build_async_anthropic_client(api_key)`
  **lazy-imports** the `anthropic` SDK (the optional `[llm]` extra) only when a real
  client is actually constructed — importing the module never requires `anthropic`.
- **Default model `claude-opus-4-8`** (the latest Claude). Operators can set
  `AGENT_MODEL=claude-sonnet-4-6` for a cheaper tier; `AGENT_MAX_TOKENS` caps output.

### 6.3 Selection and graceful fallback

`AgentService.run` (§5) uses the `llm` runtime **only** when `agent_runtime == "llm"`
**and** an `ANTHROPIC_API_KEY` is present; otherwise, and on **any** `LLMAgentError`
during a run, it falls back to the deterministic mock. `POST /api/v1/agents/run` exposes
this on the main API and persists the run; `/system/status` reports the effective
`agent_runtime`. A successful LLM run produces an `AgentRun` with the real `model_name`
and `LLM_PROMPT_VERSION`, and its evidence is **not** flagged MOCK.

### 6.4 The permanent invariant

**Agents have NO order authority — under either runtime.** The `AnalysisAgent` protocol
grants none, and `LLMAgent` adds no submit/order surface (its system prompt also states
"You ONLY analyse — you have no authority to place orders"). Only the deterministic Risk
Engine can gate orders; the analysis layer's job ends at emitting findings. A breaking
change to the finding shape (and only such a change) bumps `AGENT_FINDING_SCHEMA_VERSION`.
