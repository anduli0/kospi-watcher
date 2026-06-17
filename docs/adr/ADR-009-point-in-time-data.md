# ADR-009: point-in-time 데이터 모델 (룩어헤드 방지)

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 전략 백테스트와 실시간 신호를 동일한 데이터 모델 위에서 다룬다. 백테스트에서 가장 흔하고 치명적인 오류는 룩어헤드 바이어스(look-ahead bias) — 과거 시점에는 아직 알 수 없었던 미래 데이터가 그 시점의 의사결정에 유입되는 것이다. 예를 들어 공시·뉴스·거시 지표는 사건 발생 시각, 발표 시각, 투자자가 실제로 알 수 있었던 시각이 모두 다른데, 이를 구분하지 않으면 "발표 전에 발표 내용을 알고 거래한" 비현실적 백테스트가 만들어진다. 또한 timezone-naive datetime은 시점을 모호하게 만들어 같은 오류를 유발한다.

스펙 §8(데이터 시점 원칙)은 모든 데이터 모델이 `event_time`(사건 발생), `published_at`(발표), `available_at`(투자자가 최초로 알 수 있었던 시각), `ingested_at`(시스템 수집)을 구분할 수 있어야 한다고 규정한다. 또한: 모든 datetime은 timezone-aware, 내부 저장은 UTC, 사용자 화면은 Asia/Seoul, point-in-time 백테스트 가능, `available_at` 이후에만 전략에서 사용 가능, 미래 데이터가 과거 백테스트에 유입되지 않게 한다. 스펙 테스트 #2는 "timezone-naive datetime이 거부되는지 검사"를 요구한다.

## Decision

모든 금융 데이터에 **네 가지 시점**을 보존하고, **`available_at` 게이트**로 룩어헤드를 차단한다.

1. **네 시점 보존.** 시점이 의미 있는 모든 도메인 모델은 `event_time`, `published_at`, `available_at`, `ingested_at`을 구분해 저장한다. 의미: event_time(실제 발생), published_at(외부 발표), available_at(당시 투자자가 최초로 알 수 있던 시각), ingested_at(시스템 수집).
2. **available_at 게이트.** 전략·백테스트는 평가 시점 `T`에 대해 `available_at <= T`인 데이터만 사용한다. 미래 데이터가 과거 의사결정에 유입되지 않도록, 데이터 조회 자체를 point-in-time로 제한한다. 에이전트 evidence의 `available_at`(ADR-004)도 이 원칙과 정합한다.
3. **timezone-aware 강제.** 모든 datetime은 timezone-aware여야 하며, naive datetime은 검증 단계에서 거부한다(스펙 테스트 #2). DB 컬럼은 `DateTime(timezone=True)`를 사용한다(ADR-003 이식성).
4. **UTC 저장 / Seoul 표시.** 내부 저장은 UTC를 원칙으로 한다. 사용자 화면은 Asia/Seoul로 변환해 표시한다. 저장과 표시의 시간대 책임을 명확히 분리한다.
5. **백테스트 재현성.** 동일 입력·동일 시점이면 동일 결과가 나오도록, 데이터 접근 계층이 시점 일관성을 보장한다.

## Consequences

- 백테스트가 현실적으로 변한다. 발표 전 정보로 거래하는 룩어헤드가 구조적으로 차단되어, 전략 성과 평가의 신뢰도가 높아진다.
- 모든 시점이 명시적이라, "왜 이 시점에 이 데이터를 썼는가"를 사후 설명·재현할 수 있다(Audit/디버깅에 유리, ADR-006 연계).
- 네 시점을 모두 채워야 하므로 데이터 수집(adapter) 부담이 늘고, 일부 소스는 available_at 추정이 필요하다. 추정 시 보수적으로(늦게 알았다고) 잡아 룩어헤드를 피한다.
- timezone-aware·UTC 규율을 전 계층에서 지켜야 하며, naive datetime이 한 곳이라도 새어들면 시점 정합이 깨진다. 검증 테스트로 회귀를 막는다.
- UTC 저장 / Seoul 표시 분리로, 서머타임 없는 KST 환경에서도 시간대 혼동을 예방한다.

## Alternatives Considered

- **단일 timestamp만 저장(rejected).** "발생/발표/가용/수집"을 하나의 시각으로 뭉갬. 단순하나 룩어헤드를 막을 수 없고 스펙 §8을 위반한다. 기각.
- **naive datetime + 암묵적 KST 가정(rejected).** 시간대를 코드 관례로만 가정. 경계(외부 데이터/표시)에서 혼동이 발생하고 테스트 #2를 통과하지 못한다. timezone-aware + UTC 저장으로 대체.
- **available_at 게이트 없이 ingested_at만으로 컷오프(considered, not chosen).** 수집 시각으로 백테스트 가용성을 판단. 구현은 쉽지만, 발표는 됐으나 수집이 늦은(또는 빠른) 데이터에서 가용성 판단이 왜곡된다. 투자자 관점의 `available_at`이 룩어헤드 방지에 정확하므로 available_at 게이트를 채택했다.
