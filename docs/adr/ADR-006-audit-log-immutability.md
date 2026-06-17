# ADR-006: Audit Log 불변성 원칙

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 분석→Proposal→RiskDecision→ApprovedOrder→주문 제출→체결→대사로 이어지는 금융 의사결정 체인을 다룬다. 사고·분쟁·규제 대응 시 "누가, 언제, 어떤 근거로, 어떤 결정을 했는가"를 사후에 신뢰성 있게 재구성할 수 있어야 한다. 만약 Audit Log가 일반 애플리케이션 흐름에서 수정·삭제될 수 있다면, 사고 은폐나 사후 조작이 가능해지고 감사 가치가 사라진다.

스펙 §14는 "Audit Log는 일반 애플리케이션 흐름에서 임의 삭제할 수 없도록 설계한다"(원칙 11), "실거래 관련 설정 변경은 별도 감사 로그 대상이다"(원칙 12)를 요구한다. 스펙 §13은 `audit_logs`를 Phase 1 우선 테이블로 둔다. 스펙 §20은 `GET /api/v1/audit-logs`를 개발용 조회 API로 두되 민감정보를 제외하고 pagination을 적용한다. 스펙 테스트 #15는 "Audit Log가 중요 상태 변경을 기록하는지 검사"를 요구한다.

## Decision

Audit Log를 **append-only(추가 전용) 불변 기록**으로 설계하고, 중요한 상태 변경을 빠짐없이 남긴다.

1. **Append-only 설계.** `audit_logs` 테이블은 일반 애플리케이션 흐름에서 UPDATE/DELETE를 허용하지 않는다. 도메인 코드는 감사 항목을 추가(insert)만 하며, 수정/삭제 경로를 제공하지 않는다. 운영 DB 수준에서도 권한 최소화·트리거 등으로 변조를 어렵게 하는 것을 권장한다(THREAT_MODEL 연계).
2. **무엇을 기록하는가.** 다음과 같은 중요 상태 변경을 기록한다: 에이전트 실행, OrderProposal 생성, RiskDecision 발급(APPROVED/REJECTED), ApprovedOrder 생성, 주문 상태 전이, 대사 결과, Kill Switch 작동, 그리고 실거래 관련 설정 변경(TRADING_MODE/LIVE_TRADING_ENABLED 등). 각 항목은 시각(timezone-aware, UTC 저장 — ADR-009), 행위 주체, 대상, 이전/이후 상태, 사유를 담는다.
3. **민감정보 배제.** 브로커 키·계좌번호·토큰·비밀번호 등 비밀값은 Audit Log에 기록하지 않는다. `GET /api/v1/audit-logs`는 pagination을 적용하고 민감정보를 제외해 반환한다(스펙 §14, §20; 테스트 #11).
4. **상태 머신과 결합.** 주문 상태 머신(ADR 연계: 13상태)의 모든 합법 전이가 Audit Log에 남도록 하여, 불법 전이 시도(예외 발생)와 합법 전이가 모두 추적되게 한다.

## Consequences

- 의사결정 체인 전체가 사후 재구성 가능해진다. 사고·분쟁·규제 대응 시 신뢰할 수 있는 단일 사실 출처(source of truth)를 확보한다.
- append-only이므로 "수정"이 필요한 경우에도 새 항목을 추가하는 방식(정정 기록)을 써야 한다. 이는 기록의 진본성을 위해 의도된 제약이다.
- 기록이 계속 쌓이므로 저장 비용·보존 정책(retention)이 필요하다. 운영 단계에서 아카이빙/파티셔닝으로 대응한다.
- 비밀값을 절대 남기지 않는 규율이 필요하다. 로깅 경로 전반에서 secret redaction을 강제한다(스펙 §14, 테스트 #11과 연계).
- ADR-001/005/010과 결합해, 안전 결정(분리·게이트·deny-by-default)이 모두 불변 기록으로 뒷받침된다.

## Alternatives Considered

- **일반 mutable 테이블 + 애플리케이션 규칙(rejected).** 평범한 테이블에 "수정하지 말자"는 관례만 둠. 코드 실수·악의로 쉽게 깨지고 스펙 §14-11을 만족하지 못한다. 기각.
- **외부 SIEM/로그 수집기에만 의존(considered, not chosen).** 애플리케이션 DB엔 남기지 않고 외부 로그 파이프라인으로만 보냄. 운영 관측엔 유용하나, 도메인 트랜잭션과 같은 일관성 경계에서 감사 기록을 보장하기 어렵고 이번 Phase 범위를 벗어난다. DB append-only를 1차로 두고 외부 수집을 향후 확장(OpenTelemetry 등)으로 남긴다.
- **블록체인/해시체인 기반 변조 방지(considered, not chosen).** 각 항목을 해시 체인으로 묶어 변조를 암호학적으로 탐지. 강력하나 이번 Phase엔 과한 복잡도다. append-only + 권한 최소화로 시작하고, 필요 시 해시체인을 후속 강화책으로 둔다.
