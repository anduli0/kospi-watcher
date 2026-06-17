# ADR-015: 실 LLM(Anthropic) 에이전트 런타임 — 강제 도구 기반 구조화 출력 + mock 폴백

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER의 분석 계층은 21개 에이전트가 단일 버전드 `AgentFinding`을 산출하는 고정 카탈로그다(AGENT_DESIGN). 본래 런타임은 결정론적 `MockAgent`뿐이었다(실 Anthropic 호출 없음). 이제 실제 시장 분석 품질을 얻기 위해 진짜 LLM(Anthropic Claude)으로 finding을 생성하되, 다음을 동시에 만족해야 한다.

요구사항: (a) LLM 출력은 항상 **구조화·스키마 정합**해야 한다(자유 텍스트 파싱 금지) — 결정론 영역으로 넘어오는 LLM 산출물은 버전드 스키마 검증을 통과해야 한다(TRADING_SAFETY §3.4). (b) 신뢰 필드(에이전트 이름/버전·시각·모델·스키마 버전·근거 `source_id`)는 **모델이 아니라 코드가** 채워, finding이 항상 well-formed·scorable하도록 한다. (c) `anthropic` SDK·API 키 없이도 오프라인/CI에서 테스트 가능해야 한다. (d) LLM 오류·키 부재 시 **우아하게 mock으로 폴백**하여 시스템이 항상 결과를 반환한다. (e) 최신 Claude를 기본 모델로 하되 운영자가 더 저렴한 티어로 바꿀 수 있어야 한다. (f) 가장 중요한 불변식: **에이전트는 어떤 런타임에서도 주문 권한이 없다**(ADR-001, 절대 원칙). 본 결정은 ADR-004(에이전트 structured output)를 Anthropic 도구 호출로 구체화한다.

## Decision

실 Anthropic 백엔드 `LLMAgent`를 도입하되, 강제 도구 호출로 구조화 출력을 보장하고, 클라이언트를 주입하며, 실패 시 결정론적 mock으로 폴백한다. 에이전트의 무권한 원칙은 유지한다.

1. **강제 도구 기반 구조화 출력.** `LLMAgent.generate`(`domain/agents/llm_agent.py`)는 단일 `emit_finding` 도구와 함께 `tool_choice={"type": "tool", "name": "emit_finding"}`로 `messages.create`를 호출한다. 모델은 **반드시** 정확히 하나의 구조화 finding을 도구 입력으로 반환해야 한다(자유 텍스트 경로 없음). 도구의 `input_schema`는 `direction`/`impact`/`horizon`/`data_quality`를 enum 값 집합으로 제약하고 `direction`·`impact`·`confidence`·`thesis`를 필수로 둔다. 첫 `tool_use` 블록을 `AgentFinding`으로 파싱하며, `tool_use`가 없으면 `LLMAgentError`를 던진다.
2. **서버가 신뢰 필드를 채운다.** 에이전트 이름/버전, `as_of`/`created_at`, `model_name`, `schema_version`, 각 근거의 `source_id`(`LLM-<model>-<i>`)는 **코드에서** 설정한다(모델 입력으로 받지 않는다). `confidence`는 `[0,1]`로 클램프하고, enum 필드는 잘못된 값이면 spec 기본값으로 폴백한다(`_coerce`). `prompt_version = LLM_PROMPT_VERSION = "llm-2026.06"`. 이로써 finding은 항상 well-formed·scorable하다.
3. **클라이언트 주입 + 지연 임포트.** Anthropic 클라이언트는 `LLMAgent`에 주입되어 가짜 클라이언트로 오프라인 단위 테스트가 가능하다. `build_async_anthropic_client(api_key)`는 실제 클라이언트를 만들 때만 `anthropic` SDK를 **지연 임포트**한다 — 모듈 임포트 자체는 `anthropic` 설치를 요구하지 않는다. SDK는 선택적 extra `[llm]`로 둔다(`anthropic>=0.49`).
4. **런타임 선택 + 우아한 폴백(`agent_service/service.py`).** `AgentService.runtime_name`은 `agent_runtime == "llm"` **그리고** `ANTHROPIC_API_KEY` 존재일 때만 `"llm"`, 아니면 `"mock"`이다. `run(...)`(async)은 `llm`일 때 `LLMAgent`로 생성하되, **어떤 `LLMAgentError`에서도** `run_mock`으로 폴백한다(`agent_service.llm_fallback` 경고 로그). 미존재 이름은 여전히 `AgentNotFoundError`.
5. **설정·엔드포인트.** 설정: `agent_runtime`(`"mock"|"llm"`), `agent_model`(기본 `claude-opus-4-8`), `agent_max_tokens`(기본 2048). `POST /api/v1/agents/run`이 구성된 런타임을 실행·영속화하고, `/system/status`는 유효 `agent_runtime`을 보고한다. 기본 모델은 최신 Claude(`claude-opus-4-8`)이며, 운영자는 `AGENT_MODEL=claude-sonnet-4-6` 등 더 저렴한 티어로 바꿀 수 있다.
6. **무권한 불변식 유지.** `LLMAgent`는 어떤 submit/order 표면도 추가하지 않는다. 시스템 프롬프트도 "You ONLY analyse — you have no authority to place orders"를 명시한다. 주문 게이트는 오직 deterministic Risk Engine이며, 분석 계층의 임무는 finding 산출에서 끝난다.

## Consequences

- 실제 Claude 기반 분석 품질을 얻으면서도, 강제 도구 호출로 출력이 항상 스키마 정합이라 결정론 영역에서 안전하게 소비된다. 신뢰 필드를 코드가 채우므로 모델이 메타데이터를 위조하거나 누락할 수 없다.
- 클라이언트 주입 + 지연 임포트로, `anthropic` 미설치·키 부재 환경에서도 모듈 임포트와 테스트가 깨지지 않는다. `[llm]` extra를 설치한 운영 환경에서만 실 호출이 일어난다.
- LLM 오류·키 부재 시 mock으로 폴백하므로 시스템은 항상 well-formed `AgentRun`을 반환한다(가용성·결정론 폴백). 성공한 LLM 실행의 근거는 MOCK으로 표기되지 않으며 실제 `model_name`을 담는다.
- 기본 모델 `claude-opus-4-8`은 품질이 높지만 비용·지연이 크다. 고빈도 실행에는 `AGENT_MODEL`로 더 저렴한 티어(`claude-sonnet-4-6`)를 쓸 수 있게 하여 비용을 조절한다.
- **에이전트는 여전히 주문 권한이 없다.** 실 LLM 도입이 LLM↔실행 분리(ADR-001)·TRADING_SAFETY §3을 바꾸지 않는다. LLM 출력은 신뢰 불가 입력으로 취급되며, 자금 결정은 결정론적 코드만 내린다.
- finding 형상의 파괴적 변경(그리고 오직 그런 변경)만 `AGENT_FINDING_SCHEMA_VERSION`을 올린다. 런타임 교체(mock↔llm)는 카탈로그 계약(이름·버전·카테고리)이나 스키마를 바꾸지 않는다.

## Alternatives Considered

- **자유 텍스트 → JSON 파싱(rejected).** 모델이 JSON을 텍스트로 출력하게 하고 파싱하는 방식은 형식 오류·부분 출력·환각 필드에 취약하다. 강제 도구 호출(`tool_choice`)로 구조화 출력을 보장한다(ADR-004 구체화).
- **모델이 모든 finding 필드를 채우게 허용(rejected).** 편하지만 `source_id`·타임스탬프·모델명 등 신뢰 필드를 모델이 위조/누락할 수 있어 scorability·감사 정합이 깨진다. 신뢰 필드는 서버가 채운다.
- **`anthropic`를 필수 의존성으로(rejected).** 모든 환경에 SDK 설치를 강제하면 오프라인/CI·무LLM 운영이 무거워진다. 선택적 `[llm]` extra + 지연 임포트로 분리한다.
- **LLM 실패 시 에러 반환(considered, not chosen).** 단순하지만 일시적 LLM 장애가 분석 파이프라인을 멈춘다. mock 폴백으로 항상 결과를 보장하고, 폴백을 로그로 가시화한다.
- **기본 모델을 저렴한 티어로(considered, not chosen).** 비용은 낮지만 기본 분석 품질이 떨어진다. 기본은 최신 Claude(`claude-opus-4-8`)로 두고, 비용 민감 운영은 `AGENT_MODEL` 오버라이드로 해결한다.
- **에이전트에 제한적 주문 권한 부여(rejected, 영구).** 절대 원칙 위반. 어떤 런타임도 주문 권한을 갖지 않는다(ADR-001).
