# ADR-004: 에이전트 Structured Output 사용

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 최종적으로 21개 분석 에이전트(Market Data Integrity, News Deduplication, Korea Macro, FX, Foreign and Institutional Flow, Red-Team and Risk, Chief Market Synthesizer 등)를 운용한다. 이들의 출력은 하류(downstream)에서 Market Regime Engine, Strategy Engine, 그리고 최종적으로 Risk Engine과 사용자 화면으로 흘러간다. LLM의 자유 서술(free-form text)을 그대로 받으면 파싱이 불안정하고, 필수 근거(source_id) 누락·필드 결측을 탐지할 수 없으며, 버전 간 호환성을 보장할 수 없다.

스펙 §2는 "모든 에이전트 출력은 버전이 있는 JSON Schema를 사용한다"(원칙 14)를 요구한다. 스펙 §7은 모든 에이전트 출력이 최소한 `agent_name, agent_version, as_of, horizon, direction, impact, confidence, thesis, evidence, counterevidence, affected_sectors, affected_symbols, invalidation_conditions, data_quality, model_name, prompt_version, created_at`를 포함하고, evidence는 최소한 `source_id, source_type, title, url, published_at, available_at, claim`을 포함하며, "출처가 없는 주장은 최종 점수에 반영하지 않는다"는 원칙을 못박는다. 오버레이 E항은 `AgentFinding`·`Evidence`에서 `source_id`를 필수로 둔다.

이번 Phase에서는 실제 Anthropic API 호출 없이 mock agent로 스키마·검증만 구성한다(스펙 §7).

## Decision

모든 에이전트 출력을 **버전이 있는(versioned) JSON Schema**로 규정하고, Pydantic 모델로 강제 검증한다.

1. **Pydantic 모델 = 스키마의 단일 출처.** `AgentFinding`, `Evidence`, `AgentRun`을 Pydantic 모델로 정의하고, 여기서 JSON Schema를 생성한다(스펙 테스트 #14: AgentFinding JSON Schema가 정상 생성되는지 검사). 출력 필드는 스펙 §7의 전체 목록을 포함한다.
2. **필수 근거 강제.** `Evidence.source_id`를 필수 필드로 두어, source_id 없는 evidence가 거부되게 한다(스펙 테스트 #3). "출처 없는 주장은 최종 점수에 반영하지 않는다"는 원칙을 모델·문서에 명시한다.
3. **confidence와 impact 분리.** 신뢰도(confidence, 주장의 확실성)와 영향도(impact, 시장에 미칠 크기)를 별개 필드로 둔다. 둘을 혼동하면 약한 근거의 큰 주장이 과대평가되므로 구조적으로 분리한다.
4. **버전 보존.** 각 산출물은 `agent_version`, `model_name`, `prompt_version`을 기록한다. 스키마가 바뀌면 버전을 올리고, 과거 산출물은 자신이 생성된 버전으로 해석 가능하게 한다.
5. **점-시점 정합.** `as_of`, `horizon`과 evidence의 `published_at`/`available_at`을 통해 point-in-time(ADR-009) 원칙과 정합하게 한다. timezone-aware datetime만 허용한다(ADR-009).
6. **mock 우선.** 이번 Phase에서는 mock agent가 위 스키마를 만족하는 출력을 생성하고, validation test로 스키마 적합성을 검증한다. 실 Anthropic 호출은 하지 않으며, mock 데이터는 실데이터로 위장하지 않는다.

## Consequences

- 모든 에이전트 출력이 기계 검증 가능(machine-validated)해진다. 결측·형식 오류·source_id 누락이 입력 경계에서 거부된다.
- versioned schema 덕에 에이전트/프롬프트/모델 변경을 추적·재현할 수 있고, 과거 산출물의 의미가 보존된다.
- confidence/impact 분리로 Red-Team Agent와 Chief Synthesizer가 "약한 근거의 큰 주장"을 식별·감점하기 쉬워진다.
- Pydantic 모델을 단일 출처로 두면 JSON Schema·API 직렬화·DB 매핑이 일관된다. 다만 스키마 변경 시 버전 관리와 마이그레이션 부담이 생긴다.
- 향후 실 Anthropic Structured Output(Tool Use/JSON mode)으로 전환할 때, 동일 Pydantic 스키마를 그대로 출력 계약으로 재사용할 수 있다.

## Alternatives Considered

- **자유 서술 + 사후 파싱(rejected).** LLM이 자연어로 답하고 정규식/휴리스틱으로 추출. 가장 유연하지만 불안정하고, source_id 필수성·필드 완전성·버전 호환을 보장할 수 없어 스펙 §2-14/§7 위반. 기각.
- **버전 없는 고정 JSON(rejected).** JSON은 쓰되 스키마 버전을 두지 않음. 단기엔 단순하나, 스키마가 진화하면 과거 산출물 해석이 깨지고 회귀를 추적할 수 없다. 스펙이 "버전이 있는" 스키마를 명시하므로 기각.
- **JSON Schema를 손으로 직접 작성(considered, not chosen).** Pydantic 없이 raw JSON Schema 파일을 유지. 런타임 검증·직렬화·타입 힌트를 별도로 구현해야 하고 모델과 스키마가 어긋날 위험이 있다. Pydantic을 단일 출처로 두는 편이 정합성이 높아 채택하지 않았다.
