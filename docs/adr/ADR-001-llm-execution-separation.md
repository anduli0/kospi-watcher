# ADR-001: LLM Agent와 주문 실행 계층 분리

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 한국 증시를 LLM 기반 분석 에이전트로 해석하고, 향후 증권사 계좌와 연결해 KOSPI/KOSPI200 연계 ETF의 모의매매 및 리스크 통제형 자동매매를 수행하는 시스템이다. LLM(Anthropic API)은 본질적으로 비결정적(non-deterministic)이며, prompt injection·악성 뉴스/공시 콘텐츠·hallucination에 취약하다. 만약 LLM 에이전트가 브로커 주문 API를 직접 호출할 수 있다면, 조작된 입력 하나로 실계좌에서 비정상 주문이 발생할 수 있다. 이는 금융 시스템에서 절대 허용할 수 없는 위험이다.

스펙 §2(절대적 아키텍처 원칙)는 다음을 못박는다: LLM 에이전트는 증권사 주문 API를 직접 호출할 수 없고(원칙 1), 시장 분석 결과와 Trade Proposal만 생성하며(원칙 2), 모든 주문은 deterministic Risk Engine의 승인을 받아야 하고(원칙 3), Execution Gateway는 Agent Service와 별도 서비스로 격리하며(원칙 5), Agent Service는 `BrokerAdapter.submit_order()`에 접근할 수 없다(원칙 6). 운영 환경에서 LLM/Claude Code가 실계좌 주문 권한을 갖지 않게 해야 한다(원칙 20).

따라서 "어디서 분석이 끝나고 어디서 실행이 시작되는가"라는 경계를 코드 구조·서비스 토폴로지·타입 시스템 세 층위에서 강제할 필요가 있다.

## Decision

LLM 분석 영역과 주문 실행 영역을 명확히 분리하고, 그 경계를 다음과 같이 강제한다.

1. **책임 분리.** LLM 영역(`apps/agent-service`, `src/kospi_watcher/domain/agents`)은 뉴스·공시·거시·수급·섹터·종목 분석과 근거/반대 근거/불확실성/영향도 산출, 그리고 `OrderProposal` 생성까지만 담당한다. 가격·포지션·수량 계산, 리스크 검증, 주문 승인/제출, 체결 대사, 손익 계산, Kill Switch는 모두 비LLM(deterministic) 영역에서 순수 코드로 수행한다.

2. **타입 게이트.** `OrderProposal`은 누구나 만들 수 있으나, `ApprovedOrder`는 `RiskDecision`(status=APPROVED) 없이는 팩토리에서 생성 불가하며 생성 시도 시 예외를 raise한다. 브로커 인터페이스 메서드는 `submit_order(order: ApprovedOrder)`로, 타입 시그니처 자체가 "승인된 주문만 제출 가능"을 표현한다.

3. **서비스 격리.** `Execution Gateway`(`apps/execution-gateway`)를 Agent Service와 별도 서비스로 둔다. `submit_order` 구현은 `domain/execution/broker`와 `apps/execution-gateway`에만 존재한다. `apps/agent-service`와 `domain/agents` 소스에는 `submit_order` import 경로가 존재하지 않도록 구조화한다.

4. **구조적 검증 테스트.** Agent Service 소스에 대한 문자열/AST 스캔 + import 단언 테스트(스펙 테스트 #8)를 작성해, 에이전트 계층이 `submit_order`에 접근할 수 없음을 CI에서 회귀 방지한다.

5. **기본 비활성화.** `TRADING_MODE=RESEARCH`, `LIVE_TRADING_ENABLED=false`, `AUTO_EXECUTION_ENABLED=false`가 기본값이며, 환경변수 하나만 바꿔 실거래가 켜지는 구조를 만들지 않는다.

## Consequences

- 조작된 LLM 출력이 발생해도 그 영향이 `OrderProposal` 생성까지로 한정된다. 모든 Proposal은 deterministic Risk Engine(ADR-010)을 통과해야만 실행 단계로 갈 수 있다.
- "분석은 LLM, 결정은 코드"라는 경계가 타입·서비스·테스트 세 층에서 다중 방어된다. 한 층이 뚫려도 나머지가 막는다.
- 서비스가 분리되어 배포·네트워크 토폴로지가 다소 복잡해진다. agent-service와 execution-gateway가 별도 프로세스/컨테이너로 떠야 한다. 이 복잡도는 안전을 위한 의도된 비용으로 수용한다.
- Audit Log(ADR-006)와 결합해, Proposal→RiskDecision→ApprovedOrder의 전 흐름이 불변 기록으로 남는다.

## Alternatives Considered

- **단일 서비스 내 권한 플래그로 분리(rejected).** 하나의 프로세스 안에서 "에이전트는 실행 함수 호출 금지"를 런타임 권한 체크로만 막는 방식. 코드가 같은 주소 공간에 있으면 실수·악용으로 우회되기 쉽고, AST 수준에서 import 부재를 보장할 수 없다. 금융 안전 요구에 미달하여 채택하지 않았다.
- **LLM에게 제한된 주문 도구(tool)를 부여(rejected).** Anthropic Tool Use로 "검증된 주문만" 호출하게 하는 방안. 그러나 도구 호출 인자 자체가 비결정적 LLM이 만든 값이고 prompt injection으로 오염될 수 있어, 결정적 Risk Engine 선행 승인 원칙(스펙 §2-3)과 양립하지 않는다. 기각.
- **사람 승인만으로 통제(partially adopted).** GUARDED_LIVE 모드의 사람 승인은 채택하되, 그것만으로는 부족하다. 사람은 피로·오판할 수 있으므로 deterministic Risk Engine의 선행 승인을 1차 방어선으로 두고 사람 승인을 추가 게이트로 둔다.
