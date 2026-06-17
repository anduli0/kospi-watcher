# ADR-010: deny-by-default Risk Engine

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER에서 주문을 실제로 승인하는 주체는 LLM이 아니라 deterministic Risk Engine이다(ADR-001). Risk Engine은 허용 종목·전략, 시장 개장 상태, 데이터/호가 최신성, 주문 가격 이탈, 최대 주문 금액·포지션·총노출, 일일 손실 한도, 누적 낙폭, 전략별 손실, 일일 거래 횟수, 슬리피지, 미체결 수, 계좌 대사 상태, 중복 주문, 변동성 급등, API 장애, 데이터 신뢰도, ETF 괴리율·iNAV 등 다수의 검사를 수행한다(스펙 §11). 이런 시스템에서 기본값이 "허용"이면, 새 종목·전략·미처리 케이스가 무심코 통과해 사고로 이어진다. 안전 임계 시스템의 기본값은 반드시 "거부"여야 한다.

스펙 §2는 모든 주문이 deterministic Risk Engine의 승인을 받아야 하고(원칙 3), Risk Engine은 LLM 없이 순수 코드와 명시적 규칙으로 구현한다(원칙 4)고 못박는다. 스펙 §11은 Phase 0/1 범위로 RiskEngine 인터페이스, RiskDecision 모델, 기본 deny-by-default 정책, "명시적으로 승인되지 않은 주문은 모두 거절", 테스트용 최소 규칙, `risk_limits.yml` 초안, 리스크 변경 시 ADR/변경 로그를 요구한다. 오버레이 E항은 `ApprovedOrder`가 APPROVED `RiskDecision` 없이는 생성 불가(팩토리 raise)임을 명시한다. 스펙 테스트 #5는 "deny-by-default Risk Engine이 미등록 종목을 거절하는지", 테스트 #4는 "RiskDecision 없이 ApprovedOrder가 될 수 없는지"를 요구한다.

## Decision

Risk Engine을 **deny-by-default(기본 거부)** 의 순수 결정적(deterministic) 코드로 구현하고, 명시적으로 승인된 경우에만 통과시킨다.

1. **기본 거부.** 어떤 OrderProposal도 명시적 규칙을 모두 통과하지 않으면 거절한다. 미등록 종목·미승인 전략·미처리 케이스·규칙 부재는 전부 deny로 귀결된다(스펙 테스트 #5).
2. **LLM 미사용.** Risk Engine은 LLM을 호출하지 않는다. 순수 코드 + 명시적 규칙 + `risk_limits.yml` 설정으로만 판정한다. 동일 입력엔 동일 결정을 내리는 결정성을 보장한다.
3. **RiskDecision 산출.** 평가 결과는 `RiskDecision`(APPROVED/REJECTED + 사유)으로 표현한다. `ApprovedOrder`는 APPROVED 상태의 `RiskDecision` 없이는 팩토리에서 생성 불가하며, 없으면 예외를 raise한다(스펙 테스트 #4; ADR-001 타입 게이트).
4. **이번 Phase 범위.** RiskEngine 인터페이스, RiskDecision 모델, deny-by-default 기본 정책, 테스트용 최소 규칙, `risk_limits.yml` 초안만 구현한다. 스펙 §11의 전체 검사 목록은 향후 단계에서 확장하되, 추가 시에도 기본값은 deny를 유지한다.
5. **리스크 변경의 거버넌스.** 리스크 규칙/한도 변경은 ADR 또는 변경 로그를 남기고, 실거래 관련 변경은 Audit Log 대상이다(ADR-006). 테스트를 통과시키기 위해 리스크 통제를 약화하지 않는다(스펙 §2-18).

## Consequences

- 새 종목·전략·미처리 경로가 "자동 허용"되는 사고 경로가 사라진다. 통과는 명시적 허용을 요구하므로 안전 측으로 실패(fail-safe)한다.
- Risk Engine이 결정적이라 동일 입력에 동일 판정을 내려, 감사·재현·테스트가 쉬워진다. LLM 비결정성이 승인 경로에 끼어들지 않는다(ADR-001 정합).
- `ApprovedOrder` 생성이 RiskDecision에 강하게 결합되어, 승인 없는 주문이 타입 수준에서 만들어질 수 없다.
- deny-by-default는 초기에 "정상 주문도 막히는" 마찰을 만든다. 허용 종목·전략·한도를 명시적으로 등록해야 하므로 설정 부담이 있으나, 이는 안전을 위한 의도된 비용이다.
- 규칙이 늘수록 설정(`risk_limits.yml`)과 거버넌스(변경 로그)가 중요해진다. 변경을 추적하지 않으면 통제가 조용히 약화될 수 있으므로 ADR/Audit로 못박는다.

## Alternatives Considered

- **allow-by-default + 블랙리스트(rejected).** 기본 허용하고 위험한 것만 차단. 편의는 높으나, 누락된 규칙·새 케이스가 무심코 통과해 금융 사고를 부른다. 안전 임계 시스템 원칙과 스펙 §11(deny-by-default)에 정면 위배. 기각.
- **LLM 보조 리스크 판정(rejected).** 일부 모호한 케이스를 LLM에 위임. 비결정적이고 prompt injection·hallucination에 취약해 승인 경로에 둘 수 없다. 스펙 §2-4를 위반. 기각.
- **규칙 엔진(외부 rules DSL) 도입(considered, not chosen).** 범용 룰 엔진/DSL로 규칙을 외부화. 표현력은 높으나 결정성·감사성·테스트 용이성을 직접 통제하기 어렵고 의존성이 늘어난다. 순수 코드 + `risk_limits.yml` 설정으로 시작해 결정성과 단순성을 우선했다.
