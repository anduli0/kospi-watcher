# ADR-005: PAPER와 LIVE 환경 분리

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER의 운용 모드는 RESEARCH(분석만), PAPER(모의체결/증권사 모의투자 계좌), GUARDED_LIVE(주문 전 사용자 명시 승인), AUTO_LIVE(사전 승인 전략·한도 내 자동) 네 가지다. PAPER와 LIVE는 같은 코드 경로를 공유하지만, 사용하는 계좌·자격증명·리스크 한도·체결 의미가 완전히 다르다. 만약 두 환경의 자격증명이 섞이거나, 모드 식별이 모호하면, 모의로 착각한 채 실주문을 보내는 치명적 사고가 발생할 수 있다.

스펙 §14(보안 원칙)는 "운영용 키와 모의투자 키를 분리한다"(원칙 13), "PAPER와 LIVE 환경을 분리한다"(원칙 14)를 요구한다. 스펙 §2는 환경변수 하나만 변경하여 실거래가 활성화되는 구조를 만들지 말 것(원칙 19), 운영 환경에서 LLM이 실계좌 주문 권한을 갖지 않게 할 것(원칙 20)을 못박는다. 기본값은 `TRADING_MODE=RESEARCH`, `LIVE_TRADING_ENABLED=false`, `AUTO_EXECUTION_ENABLED=false`이며, 실거래는 명시적 별도 요청 전까지 구현/활성화하지 않는다.

`.env.example`에는 KIS/Kiwoom 키 변수가 정의되며(`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NUMBER`, `KIWOOM_APP_KEY`, `KIWOOM_APP_SECRET`), 이들은 PAPER/LIVE에서 서로 다른 자격증명을 가리켜야 한다.

## Decision

PAPER와 LIVE를 명시적으로 분리하고, 실거래로의 전환을 다층 게이트로 막는다.

1. **모드의 명시적 표현.** `TRADING_MODE`(RESEARCH/PAPER/GUARDED_LIVE/AUTO_LIVE)를 enum으로 두고, 기본값 RESEARCH. PAPER와 LIVE는 같은 코드를 타되, 어떤 브로커 환경/계좌를 쓰는지가 모드에 의해 결정된다. UI는 항상 현재 모드와 "LIVE TRADING DISABLED"를 명시한다.
2. **자격증명 분리.** PAPER 자격증명과 LIVE 자격증명은 절대 공유하지 않는다. 운영용 키와 모의투자 키를 분리된 환경변수/시크릿으로 관리하고, 어떤 경로로도 PAPER 컨텍스트가 LIVE 키를 읽지 못하게 한다.
3. **다중 게이트.** 실주문은 `LIVE_TRADING_ENABLED=true` 단 하나로 켜지지 않는다. (a) `TRADING_MODE`가 LIVE 계열이고, (b) `LIVE_TRADING_ENABLED=true`이며, (c) deterministic Risk Engine이 APPROVED `RiskDecision`을 발급하고(ADR-010), (d) GUARDED_LIVE에서는 사용자의 명시적 승인이 추가로 필요하다. 환경변수 하나만으로 실거래가 켜지는 구조를 금지한다.
4. **실거래 설정 변경 감사.** 실거래 관련 설정 변경은 별도 Audit Log 대상이다(ADR-006). 모드 전환·라이브 토글은 불변 감사 기록을 남긴다.
5. **이번 Phase 범위.** 실거래·실 브로커·실 자격증명은 구현하지 않는다. PAPER/LIVE 분리는 모드 enum, 자격증명 변수 분리, 게이트 구조, mock으로만 표현한다. 기본값은 RESEARCH/false/false를 유지한다.

## Consequences

- 모의와 실거래가 자격증명·모드·게이트 수준에서 분리되어, "모의로 착각한 실주문" 사고 경로가 구조적으로 차단된다.
- 실거래 활성화가 의도적으로 번거로워진다(다중 게이트 + 사람 승인 + 감사). 편의성은 떨어지지만 안전을 위한 의도된 마찰이다.
- 운영용/모의용 키를 별도 관리해야 하므로 시크릿 운영 부담이 늘어난다. 이는 키 유출 시 폭발 반경(blast radius)을 줄이는 대가로 수용한다.
- ADR-001(LLM-실행 분리), ADR-010(deny-by-default Risk Engine), ADR-006(Audit Log)과 결합해 실거래 전환이 다중 방어선을 통과해야만 가능해진다.

## Alternatives Considered

- **단일 자격증명 + 플래그로 모드 전환(rejected).** 같은 키로 PAPER/LIVE를 토글. 가장 단순하나, 키가 한 벌이라 실수/유출 시 즉시 실계좌로 번지고, 스펙 §14-13/14를 위반한다. 기각.
- **`LIVE_TRADING_ENABLED` 단일 플래그로 충분(rejected).** 플래그 하나로 실거래 허용. 스펙 §2-19("환경변수 하나만 변경하여 실거래가 활성화되는 구조 금지")를 정면 위반한다. 다중 게이트로 대체.
- **완전 별도 배포(separate deployment) 강제(considered, not chosen).** PAPER와 LIVE를 물리적으로 분리된 별개 시스템으로 운영. 가장 안전하나 이중 운영 비용이 크고, 이번 Phase의 mock 범위엔 과하다. 대신 동일 코드베이스 내 모드/자격증명/게이트 분리로 시작하되, 운영 단계에서 환경 격리를 강화할 여지를 남긴다.
