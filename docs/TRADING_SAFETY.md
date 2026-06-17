# TRADING_SAFETY.md — KOSPI-WATCHER 트레이딩 시스템 안전 규약

> 본 문서는 KOSPI-WATCHER에서 **가장 권위 있는 안전 문서**다. 시스템의 어떤 코드·설정·운영 절차도 이 문서에 명시된 안전 원칙을 약화시키는 방향으로 변경될 수 없다.
> 권위 있는 출처는 `_KICKOFF.md` (A 오버레이 + B 스펙, 특히 §1·§2·§11·§12, 오버레이 §E)다. 본 문서와 `_KICKOFF.md`가 충돌하는 것처럼 보이면 **더 안전한 쪽**으로 해석하고, 즉시 변경 통제 절차(§13)를 따른다.
> 안전을 약화하는 어떠한 예외·우회·"임시" 조치도 본 문서에서 허용하지 않는다.

| 항목 | 값 |
| --- | --- |
| 문서 ID | DOC-TRADING-SAFETY |
| Phase | Phase 0 (설계·정책 문서) |
| 상태 | Authoritative / Active |
| 적용 범위 | 전 서비스(api, agent-service, execution-gateway, worker, web), 전 도메인 모듈 |
| 상위 규범 | `_KICKOFF.md` §1·§2·§11·§12, 오버레이 §E·§F |
| 관련 ADR | ADR-001(LLM↔주문 분리), ADR-002(Broker Adapter), ADR-005(PAPER/LIVE 분리), ADR-006(Audit Log 불변성), ADR-008(Decimal), ADR-010(deny-by-default Risk Engine), ADR-013(Yahoo 시세), ADR-014(PAPER 실행), ADR-015(LLM 에이전트 런타임) |
| 관련 문서 | `docs/THREAT_MODEL.md`, `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md`, `docs/AGENT_DESIGN.md` |

---

## 목차

1. [안전 철학과 위협 가정](#1-안전-철학과-위협-가정)
2. [실거래 기본 비활성화 & 다중 활성화 게이트](#2-실거래-기본-비활성화--다중-활성화-게이트)
3. [LLM / 주문 실행 경계](#3-llm--주문-실행-경계)
4. [Deterministic Risk Engine: deny-by-default + 22 체크리스트](#4-deterministic-risk-engine-deny-by-default--22-체크리스트)
5. [주문 상태 머신: 13상태 + 허용 전이표 + 불법 전이 예외](#5-주문-상태-머신-13상태--허용-전이표--불법-전이-예외)
6. [Idempotency Key 규약](#6-idempotency-key-규약)
7. [잔고 · 체결 대사(Reconciliation) 절차](#7-잔고--체결-대사reconciliation-절차)
8. [Kill Switch: 8 트리거 + 동작 + 복구](#8-kill-switch-8-트리거--동작--복구)
9. [PAPER / LIVE 분리(자격증명 / 계좌 / 네트워크)](#9-paper--live-분리자격증명--계좌--네트워크)
10. [GUARDED_LIVE 승인형 실거래 원칙](#10-guarded_live-승인형-실거래-원칙)
11. [AUTO_LIVE 활성화 조건(사전승인 전략 · 한도)](#11-auto_live-활성화-조건사전승인-전략--한도)
12. [Phase 0/1 현재 구현 범위와 명시적 비구현](#12-phase-01-현재-구현-범위와-명시적-비구현)
13. [변경 통제(리스크 한도 변경 시 ADR / 감사 로그)](#13-변경-통제리스크-한도-변경-시-adr--감사-로그)

---

## 1. 안전 철학과 위협 가정

### 1.1 안전 철학 (Safety Philosophy)

KOSPI-WATCHER는 **실제 자본을 운용할 수 있는 시스템**이다. 따라서 본 시스템의 기본 자세는 "분석은 똑똑하게, 실행은 보수적으로"다. 모든 설계 결정은 다음 위계를 따른다.

1. **안전 > 수익 > 편의성.** 안전을 위해 수익 기회를 포기하는 것은 항상 허용된다. 그 반대는 절대 허용되지 않는다.
2. **Fail-safe / Fail-closed.** 무엇인가 불확실하거나, 데이터가 의심스럽거나, 컴포넌트가 응답하지 않으면 시스템은 **주문을 막는 방향**으로 실패한다. 침묵하거나 추측해서 주문을 진행하지 않는다.
3. **Deny-by-default.** 명시적으로 허용되지 않은 모든 것(종목·전략·전이·주문)은 거부한다.
4. **Defense in depth (다층 방어).** 단일 컴포넌트 하나가 뚫려도 시스템 전체가 위험해지지 않도록, 독립된 게이트를 여러 겹 둔다. 어느 한 게이트도 단독으로 실거래를 켤 수 없다.
5. **Determinism for money (자금 결정은 결정론적으로).** 돈·수량·리스크·승인에 관한 모든 결정은 LLM이 아니라 순수 코드와 명시적 규칙으로 내린다.
6. **Least privilege (최소 권한).** 각 서비스는 자신의 임무에 필요한 최소 권한만 가진다. Agent Service는 주문 실행 경로에 대한 권한을 **구조적으로** 갖지 못한다.
7. **Auditability (감사 가능성).** 모든 리스크 결정·상태 전이·실거래 설정 변경은 변조 불가능한 Audit Log에 남는다. 흔적 없는 자금 행위는 존재할 수 없다.
8. **Honesty about state (상태에 대한 정직성).** mock 데이터를 실데이터로 위장하지 않는다(`"MOCK DATA — NOT REAL MARKET DATA"` 배너). 미검증 항목을 통과한 것처럼 보고하지 않는다.

### 1.2 위협 가정 (Threat Assumptions)

본 문서는 다음을 가정한다. 상세 분석은 `docs/THREAT_MODEL.md`에 있으며, 본 문서는 그 위협을 막기 위한 **운영·구조 규약**을 정의한다.

| # | 위협 가정 | 본 문서가 막는 방식 |
| --- | --- | --- |
| T1 | LLM이 환각·프롬프트 인젝션·악성 뉴스/공시에 오염되어 위험한 매매를 "제안"할 수 있다 | LLM은 제안만 가능, 주문 권한 없음(§3). 모든 제안은 deterministic Risk Engine 통과 필수(§4) |
| T2 | 코드 결함·잘못된 전략 배포로 비정상 수량·가격 주문이 생성될 수 있다 | Risk Engine 22 체크(§4) + 상태 머신 불법 전이 예외(§5) + Kill Switch(§8) |
| T3 | 네트워크 재시도·버그로 동일 주문이 중복 제출될 수 있다(Replay) | idempotency key 규약(§6) + Risk Engine 중복주문 체크 + Kill Switch 트리거 |
| T4 | 브로커 장부와 내부 장부가 어긋날 수 있다(체결 누락·부분체결) | 의무적 대사 절차(§7) + RECONCILIATION_ERROR 상태 + Kill Switch 트리거 |
| T5 | 환경변수 하나가 잘못 설정되어 실거래가 의도치 않게 켜질 수 있다 | 다중 활성화 게이트(§2) — 단일 플래그로는 절대 LIVE가 되지 않음 |
| T6 | 시세·호가 데이터가 지연·정지되어 낡은 가격으로 매매할 수 있다 | Risk Engine 데이터/호가 최신성 체크(§4) + 가격 데이터 지연 Kill Switch(§8) |
| T7 | PAPER 자격증명/계좌와 LIVE 자격증명/계좌가 혼동될 수 있다 | PAPER/LIVE 완전 분리(§9) — 자격증명·계좌·환경·네트워크 격리 |
| T8 | 운영 환경에서 LLM/Claude Code가 실계좌 주문 권한을 획득할 수 있다 | 운영 원칙상 LLM은 실계좌 주문 권한 없음(§3.6). import 격리 테스트(test #8) |
| T9 | 브로커 API가 연속 실패하거나 비정상 응답을 줄 수 있다 | Risk Engine API 장애 체크 + 브로커 연속오류 Kill Switch(§8) |
| T10 | 리스크 한도가 감사 없이 몰래 완화될 수 있다 | 변경 통제(§13) — 한도 변경은 ADR + Audit Log 의무 |

**신뢰 경계(Trust Boundary)의 핵심 가정:** LLM 출력은 **항상 신뢰할 수 없는 입력(untrusted input)** 으로 취급한다. LLM은 시스템의 "두뇌"가 아니라 "조언자"이며, 자금을 움직이는 결정은 결정론적 코드만 내린다.

---

## 2. 실거래 기본 비활성화 & 다중 활성화 게이트

### 2.1 기본값 (Hard Default)

다음 세 환경변수의 기본값은 **반드시** 아래와 같아야 한다. 이 기본값은 `.env.example`, 코드 내 설정 모델의 default, 테스트(test #6, #7)로 삼중 고정된다.

```
TRADING_MODE=RESEARCH
LIVE_TRADING_ENABLED=false
AUTO_EXECUTION_ENABLED=false
```

- `_KICKOFF.md` §1·§14의 `.env.example`은 위 값을 명시한다.
- 설정 미지정·파싱 실패·알 수 없는 값일 때의 동작은 항상 **가장 안전한 값**(`RESEARCH` / `false` / `false`)으로 폴백한다. "알 수 없으면 켠다"는 절대 없다.
- **test #6**: `LIVE_TRADING_ENABLED`가 기본 `false`인지 검사. **test #7**: `AUTO_EXECUTION_ENABLED`가 기본 `false`인지 검사. (`_KICKOFF.md` §22)

### 2.2 운용 모드 4종

| 모드 | 정의 | 주문 생성 | 실계좌 영향 | 자격증명 |
| --- | --- | --- | --- | --- |
| `RESEARCH` | 분석만 수행. 주문을 **생성하지 않는다**. | 없음 | 없음 | 불필요 |
| `PAPER` | 내부 모의체결 또는 증권사 모의투자 계좌에서 거래. | 모의 | 없음 | **PAPER 전용** 자격증명·계좌·환경(§9) |
| `GUARDED_LIVE` | 실계좌 주문 **전마다** 사용자의 명시적 승인. | 실주문(승인 후) | 있음 | **LIVE 전용** 자격증명·계좌·환경(§9) |
| `AUTO_LIVE` | **사전 승인된** 전략·한도 내에서만 자동 주문. | 실주문(정책 승인) | 있음 | **LIVE 전용** 자격증명·계좌·환경(§9) |

> **금지(절대 원칙 §19):** 환경변수 **하나만** 변경하여 실거래가 활성화되는 구조를 만들지 않는다. LIVE 진입은 아래 §2.3의 **모든** 게이트를 동시에 통과해야 한다.

### 2.3 다중 활성화 게이트 (Multi-Gate to LIVE)

`GUARDED_LIVE` 또는 `AUTO_LIVE`로의 실거래가 성립하려면 **아래 게이트가 전부(AND) 충족**되어야 한다. 하나라도 미충족이면 시스템은 PAPER/RESEARCH로 강등(다운그레이드)되며, 주문 실행 경로는 닫힌다.

| 게이트 | 조건 | 검증 주체 | 미충족 시 |
| --- | --- | --- | --- |
| G1 운용 모드 | `TRADING_MODE` ∈ {`GUARDED_LIVE`, `AUTO_LIVE`} | Config 로더 | RESEARCH로 강등 |
| G2 LIVE 플래그 | `LIVE_TRADING_ENABLED=true` | Config 로더 | 실거래 경로 차단 |
| G3 자동실행 플래그 | (`AUTO_LIVE`에 한해) `AUTO_EXECUTION_ENABLED=true` | Config 로더 | AUTO 차단(GUARDED만 가능) |
| G4 LIVE 자격증명 | LIVE 전용 broker 자격증명이 **LIVE 환경**에 존재·유효 | Execution Gateway | 실거래 경로 차단 |
| G5 환경 분리 검증 | 실행 환경이 LIVE 환경이며 PAPER 자격증명과 혼재하지 않음(§9) | Execution Gateway | 실거래 경로 차단 |
| G6 Kill Switch 비활성 | 전역 Kill Switch가 `ARMED`(정상) 상태(§8) | Execution Gateway | 전면 차단 |
| G7 Risk Engine 승인 | 해당 주문에 대해 `RiskDecision == APPROVED`(§4) | Risk Engine | 주문 거절 |
| G8 인간/정책 승인 | `GUARDED_LIVE`: 사용자 명시 승인(§10) / `AUTO_LIVE`: 사전승인 전략·한도 내(§11) | Execution Gateway + 운영자 | 주문 보류·거절 |
| G9 전략 버전 일치 | 실행 전략의 `strategy_version`이 사전 승인된 버전과 일치 | Risk Engine + Execution Gateway | 거절 + Kill Switch 검토 |
| G10 대사 정상 | 직전 주문들의 잔고·체결 대사가 일치 상태(`RECONCILIATION_ERROR` 없음, §7) | Execution Gateway | 전면 차단 |

**게이트 평가 규칙:**
- 게이트 평가는 **deny-by-default**다. 모든 게이트가 명시적으로 통과(`true`)일 때만 LIVE 경로가 열린다.
- 게이트는 **결정론적 코드**로만 평가한다. LLM은 게이트 평가에 관여하지 못한다.
- 게이트 통과/실패는 매 주문마다 Audit Log에 기록한다.

> **Phase 0/1 현실:** 본 Phase에서 LIVE 경로는 **구현되지 않는다**(§12). G1~G3 플래그는 설정·테스트로 존재하고 기본 `false`이며, G4~G10은 설계·문서로만 정의된다. `LIVE_TRADING_ENABLED=true`로 바꾸어도 실주문 코드가 존재하지 않으므로 실거래는 일어나지 않는다.

---

## 3. LLM / 주문 실행 경계

### 3.1 절대 원칙 (Inviolable)

`_KICKOFF.md` §2 절대 원칙에서 직접 도출된다.

1. **LLM 에이전트는 증권사 주문 API를 직접 호출할 수 없다.**
2. **LLM 에이전트는 시장 분석 결과와 Trade Proposal(= `OrderProposal`)만 생성한다.**
3. 모든 주문은 deterministic Risk Engine의 승인을 받아야 한다.
4. Risk Engine은 LLM 없이 순수 코드와 명시적 규칙으로 구현한다.
5. Execution Gateway는 Agent Service와 **별도 서비스**로 격리한다.
6. **Agent Service는 `BrokerAdapter.submit_order()`에 접근할 수 없다.**
7. 운영 환경에서 Claude Code 또는 LLM이 실계좌 주문 권한을 갖지 않는다.

### 3.2 경계 다이어그램 (책임 분리)

```
[LLM 영역 — 신뢰 불가, 자문만]                    [비LLM 영역 — 결정론, 자금 결정]
─────────────────────────────────                ─────────────────────────────────
 apps/agent-service                                apps/execution-gateway
 src/kospi_watcher/domain/agents                   src/kospi_watcher/domain/execution
   · 뉴스/공시/거시/수급/섹터/종목 분석                · 가격·포지션·수량 계산
   · 근거 / 반대근거 / 불확실성 / 영향도               · 리스크 검증 (Risk Engine)
   · Trade Proposal (= OrderProposal) 생성   ──┐    · 주문 승인 (RiskDecision)
                                              │    · 주문 제출 (submit_order)
                                              │    · 체결 대사 / 손익 계산
                                              │    · Kill Switch
                                              │
   OrderProposal (PROPOSED) ──────────────────┘──▶ Risk Engine ──▶ RiskDecision
       (주문 권한 없음)                                              │
                                                  (APPROVED 일 때만)  ▼
                                                            ApprovedOrder (factory)
                                                                     │
                                                                     ▼
                                                            BrokerAdapter.submit_order
                                                            (Execution Gateway 전용)
```

**핵심:** Agent Service에서 나오는 산출물은 `OrderProposal`(상태 `PROPOSED`)이 **최대치**다. `OrderProposal`은 그 자체로는 어떤 자금 행위도 일으키지 못한다. `ApprovedOrder`로의 승격은 오직 Risk Engine의 `APPROVED` 결정을 통해, Execution Gateway 측 팩토리에서만 일어난다.

### 3.3 코드로 강제하는 방법 (Enforced in Code)

본 경계는 "지키자"는 약속이 아니라 **코드 구조와 테스트로 강제**된다.

**(a) Import 격리 (Import Isolation)**
- `submit_order` 구현은 **오직** `src/kospi_watcher/domain/execution/broker` 와 `apps/execution-gateway` 에만 둔다. (`_KICKOFF.md` 오버레이 §E)
- `apps/agent-service` 및 `src/kospi_watcher/domain/agents` 소스에는 `submit_order` **import 경로가 존재하지 않도록** 구조화한다. Agent 측은 `BrokerAdapter` 자체를 import하지 않는다.
- Broker별 API 명세가 전략/에이전트 코드에 직접 침투하지 않게 한다(절대 원칙 §11·§12). 전략 코드와 브로커 구현은 인터페이스(`BrokerAdapter` Protocol)로만 분리되어 만난다.

**(b) 팩토리 raise (Factory Guard)**
- `ApprovedOrder`는 **APPROVED 상태의 `RiskDecision` 없이는 생성 불가**하다. 팩토리(`ApprovedOrder.create(...)` 또는 동급의 생성 진입점)는 다음을 검증하고, 위반 시 **예외를 raise** 한다. (`_KICKOFF.md` 오버레이 §E)
  - `risk_decision`이 존재하고 그 결정이 `APPROVED`인가? 아니면 raise.
  - `idempotency_key`가 존재하는가? 없으면 raise.
  - 동일 `idempotency_key`의 중복 주문인가? 그렇다면 raise(중복 거부, §6).
- 즉, `ApprovedOrder`는 생성자(`__init__`)를 통한 임의 생성이 불가능하며, 반드시 검증 팩토리를 거친다. 검증을 우회하는 직접 인스턴스화 경로를 만들지 않는다.
- **test #4**: `OrderProposal`이 `RiskDecision` 없이 `ApprovedOrder`가 될 수 없는지 검사. (`_KICKOFF.md` §22)

**(c) 서비스 분리 (Service Isolation)**
- `apps/agent-service`와 `apps/execution-gateway`는 **별도 프로세스/서비스**다(절대 원칙 §5). docker-compose 상에서도 책임이 분리된다(`_KICKOFF.md` §23).
- 두 서비스는 **네트워크 수준에서도 분리 가능**하도록 설계한다(`_KICKOFF.md` §14-10). Agent Service는 Execution Gateway의 주문 실행 엔드포인트를 직접 호출할 권한을 갖지 않는다. 둘 사이의 유일한 정상 통신 경로는 `OrderProposal`(데이터)이며, 실행 권한이 아니다.
- `execution-gateway`는 본 Phase에서 실주문 기능 없이 실행된다(`_KICKOFF.md` §5·§23).

**(d) 테스트 #8 — Import/AST 스캔 단언 (Structural Test)**
- `_KICKOFF.md` 오버레이 §E 및 §22 **test #8**: *"Agent Service가 `BrokerAdapter.submit_order`에 접근하지 못하는지 검사."*
- 구현 위치: `tests/security/`.
- 검사 방식(둘 다 수행):
  1. **소스 문자열 / AST 스캔:** `apps/agent-service` 및 `src/kospi_watcher/domain/agents` 트리의 모든 `.py`에 대해 `submit_order` 문자열 및 import 구문이 존재하지 않음을 AST로 단언한다.
  2. **Import 단언:** Agent 측 모듈을 import한 뒤, 해당 네임스페이스에서 `submit_order` / `BrokerAdapter` 가 도달 불가능함을 단언한다.
- 이 테스트가 깨지면 빌드/CI가 실패한다. 즉, 경계 위반은 **머지 자체가 차단**된다.

### 3.4 데이터 방향 규칙

- LLM → 결정론 방향으로는 **데이터(제안)** 만 흐른다.
- 결정론 → LLM 방향으로는 분석에 필요한 시장 컨텍스트만 흐른다.
- LLM이 생성한 텍스트/JSON은 결정론 영역에 들어올 때 **항상 스키마 검증**을 거친다(버전 있는 JSON Schema, `_KICKOFF.md` §7). 검증 실패 시 제안은 폐기된다.

### 3.5 출처 없는 주장 배제

출처(`source_id`)가 없는 주장은 최종 점수·신호에 반영하지 않는다(`_KICKOFF.md` §7). `Evidence`는 `source_id`가 필수이며, 이를 강제하는 테스트(test #3)가 있다. 이는 악성/허위 콘텐츠가 자금 결정에 침투하는 경로를 좁힌다.

### 3.6 운영 원칙: LLM/Claude Code의 실계좌 권한 없음

- 운영 환경에서 **Claude Code 또는 어떤 LLM도 실계좌 주문 권한을 갖지 않는다**(`_KICKOFF.md` §2-20, §14-15).
- production secret(브로커 키·계좌번호·토큰)을 Claude Code가 **읽거나 출력하지 못한다**는 운영 원칙을 둔다(`_KICKOFF.md` §14-15). 비밀값은 코드·로그·프런트엔드·API 응답에 노출되지 않는다(test #11).

---

## 4. Deterministic Risk Engine: deny-by-default + 22 체크리스트

### 4.1 설계 원칙

- Risk Engine은 **순수 코드로 구현하며 LLM을 사용하지 않는다**(`_KICKOFF.md` §11, 절대 원칙 §3·§4). 동일 입력에 대해 항상 동일한 결정을 내리는 **결정론적** 컴포넌트다.
- **Deny-by-default:** 명시적으로 승인되지 않은 주문은 **모두 거절**한다(`_KICKOFF.md` §11, ADR-010). 22개 체크가 전부 `PASS`이고, 모든 적용 한도를 위반하지 않을 때만 `APPROVED`다.
- **테스트를 통과시키기 위해 리스크 통제를 약화하지 않는다**(`_KICKOFF.md` §2-18). 규칙이 불편하면 규칙을 우회하는 게 아니라, 변경 통제(§13)를 따른다.

### 4.2 RiskDecision 모델 (개념)

| 필드 | 의미 |
| --- | --- |
| `decision` | `APPROVED` / `REJECTED` (deny-by-default; 기본 `REJECTED`) |
| `proposal_id` | 평가 대상 `OrderProposal` 식별자 |
| `idempotency_key` | 평가 대상 주문의 idempotency key(§6) |
| `checks` | 22개 체크 각각의 결과(`PASS`/`FAIL`/`NOT_APPLICABLE`)와 사유 |
| `failed_checks` | 실패한 체크 목록(거절 사유의 근거) |
| `risk_limits_version` | 평가에 사용된 `risk_limits.yml` 버전/해시 |
| `evaluated_at` | 평가 시각(timezone-aware, UTC 저장) |
| `engine_version` | Risk Engine 버전 |

- `RiskDecision`은 **오직 Risk Engine만 생성**할 수 있다(`_KICKOFF.md` §18 CLAUDE.md: "Only Risk Engine can create RiskDecision").
- `ApprovedOrder` 팩토리는 `decision == APPROVED`인 `RiskDecision`만 받아들인다(§3.3-b).

### 4.3 22 체크리스트 (스펙 §11)

> 모든 체크는 **deny-by-default**다. 평가에 필요한 데이터가 없거나, 신선하지 않거나, 신뢰할 수 없으면 그 체크는 **FAIL** 처리하여 주문을 막는다("판단 불가 = 거절").
> 한도값의 출처는 `config/risk_limits.yml`(§13)이며, 한도 변경은 ADR + Audit Log 의무(§13)다.

| # | 체크 | 검사 내용 | FAIL → 결과 | 연동 Kill Switch |
| --- | --- | --- | --- | --- |
| 1 | 허용 종목 여부 | 주문 종목이 허용 종목 화이트리스트에 있는가 | 거절(미등록 종목 deny) | — |
| 2 | 허용 전략 여부 | 주문을 낸 전략이 허용 전략 목록에 있는가 | 거절 | — |
| 3 | 시장 개장 상태 | 해당 시장이 개장(거래 가능 시간) 상태인가 | 거절 | — |
| 4 | 데이터 최신성 | 의사결정에 쓰인 시장/지표 데이터가 허용 지연 내인가 | 거절 | 가격 데이터 지연 |
| 5 | 호가 최신성 | 주문 가격 산정에 쓰인 호가가 허용 지연 내인가 | 거절 | 가격 데이터 지연 |
| 6 | 주문 가격 이탈 | 주문 가격이 기준가 대비 허용 이탈 범위 내인가 | 거절 | — |
| 7 | 최대 주문 금액 | 단일 주문 금액이 한도 이하인가 | 거절 | — |
| 8 | 최대 포지션 | 종목별 포지션이 한도 이하가 되는가 | 거절 | — |
| 9 | 최대 총노출 | 계좌 총노출(합산)이 한도 이하가 되는가 | 거절 | — |
| 10 | 일일 손실 한도 | 당일 손실이 한도를 초과하지 않는가 | 거절 | 일일 손실 한도 초과 |
| 11 | 누적 낙폭 한도 | 누적 낙폭(MDD)이 한도 이하인가 | 거절 | — |
| 12 | 전략별 손실 한도 | 해당 전략의 손실이 전략별 한도 이하인가 | 거절 | — |
| 13 | 일일 거래 횟수 | 당일 거래 횟수가 한도 이하인가 | 거절 | — |
| 14 | 슬리피지 한도 | 예상 슬리피지가 허용치 이하인가 | 거절 | — |
| 15 | 미체결 주문 수 | 미체결(open) 주문 수가 한도 이하인가 | 거절 | — |
| 16 | 계좌 대사 상태 | 직전 대사가 일치(불일치/오류 없음) 상태인가(§7) | 거절 | 계좌 대사 불일치 |
| 17 | 중복 주문 | 동일 idempotency key/동일 의도의 중복 주문이 아닌가(§6) | 거절 | 중복 주문 감지 |
| 18 | 변동성 급등 | 대상의 변동성이 비정상 급등 상태가 아닌가 | 거절 | — |
| 19 | API 장애 | 브로커/데이터 API가 정상(연속오류 없음)인가 | 거절 | 브로커 API 연속 오류 |
| 20 | 데이터 신뢰도 | 입력 데이터의 신뢰도(data_quality)가 기준 이상인가 | 거절 | — |
| 21 | ETF 괴리율 | (ETF) 시장가-NAV 괴리율이 허용 범위 내인가 | 거절 | — |
| 22 | iNAV 이상 | (ETF) iNAV 값이 정상 범위(이상치 아님)인가 | 거절 | — |

**평가 종합 규칙:**
- 22개 중 **하나라도 FAIL**이면 `RiskDecision = REJECTED`.
- 모든 체크 PASS(또는 NOT_APPLICABLE) **그리고** 모든 적용 한도 미위반일 때만 `APPROVED`.
- 평가 결과(통과/실패 체크, 사용 한도 버전)는 Audit Log에 남긴다.

### 4.4 Phase 0/1 구현 범위 (Risk Engine)

`_KICKOFF.md` §11에 따라 본 Phase에서는 다음만 구현한다.

- `RiskEngine` 인터페이스
- `RiskDecision` 모델
- 기본 **deny-by-default 정책**(명시 승인되지 않은 주문 전부 거절)
- 테스트용 **최소 규칙**(예: 허용 종목 여부 등 일부 체크의 동작 가능한 부분)
- `config/risk_limits.yml` **초안**
- 리스크 변경 시 ADR 또는 변경 로그 필요(§13)
- **실제 계좌 주문 기능 없음**
- **test #5**: deny-by-default Risk Engine이 **미등록 종목을 거절**하는지 검사. (`_KICKOFF.md` §22)

22개 체크 **전부의 완전한 로직**은 후속 Phase에서 구현한다(§12). 본 Phase에서는 인터페이스·모델·deny-by-default·최소 규칙·한도 초안이 범위다.

---

## 5. 주문 상태 머신: 13상태 + 허용 전이표 + 불법 전이 예외

### 5.1 13개 상태 (스펙 §12)

| 상태 | 의미 |
| --- | --- |
| `PROPOSED` | Agent/전략이 `OrderProposal`을 생성. 아직 리스크 평가 전. |
| `RISK_REJECTED` | Risk Engine이 거절(종결 상태). |
| `RISK_APPROVED` | Risk Engine이 승인. (승인형/자동 분기 전 단계) |
| `AWAITING_HUMAN` | `GUARDED_LIVE`에서 사용자 명시 승인 대기. |
| `APPROVED` | 인간/정책 승인 완료. `ApprovedOrder` 성립. 제출 가능. |
| `SUBMITTING` | Execution Gateway가 브로커로 제출 진행 중. |
| `SUBMITTED` | 브로커가 주문 접수 확인. |
| `PARTIALLY_FILLED` | 일부 체결. |
| `FILLED` | 전량 체결(종결 상태). |
| `CANCEL_PENDING` | 취소 요청 전송, 브로커 확인 대기. |
| `CANCELLED` | 취소 확정(종결 상태). |
| `REJECTED` | 브로커가 주문 거부(종결 상태). |
| `RECONCILIATION_ERROR` | 잔고·체결 대사 불일치 감지(종결/격리 상태, Kill Switch 연동 §7·§8). |

### 5.2 허용 전이표 (Allowed Transitions)

> 아래에 **명시된 전이만** 허용한다. 표에 없는 전이는 전부 **불법(illegal)** 이며, 시도 시 예외를 raise 한다(§5.3). Deny-by-default가 상태 머신에도 적용된다.

| From → To | 허용 | 의미 / 트리거 |
| --- | --- | --- |
| `PROPOSED` → `RISK_REJECTED` | ✅ | Risk Engine 거절 |
| `PROPOSED` → `RISK_APPROVED` | ✅ | Risk Engine 승인 |
| `RISK_APPROVED` → `AWAITING_HUMAN` | ✅ | `GUARDED_LIVE`: 사용자 승인 대기로 진입 |
| `RISK_APPROVED` → `APPROVED` | ✅ | `AUTO_LIVE`: 사전승인 정책으로 자동 승인 |
| `AWAITING_HUMAN` → `APPROVED` | ✅ | 사용자가 명시적으로 승인 |
| `AWAITING_HUMAN` → `CANCELLED` | ✅ | 사용자가 승인 거부/철회 |
| `APPROVED` → `SUBMITTING` | ✅ | Execution Gateway 제출 시작 |
| `SUBMITTING` → `SUBMITTED` | ✅ | 브로커 접수 확인 |
| `SUBMITTING` → `REJECTED` | ✅ | 브로커가 접수 거부 |
| `SUBMITTING` → `RECONCILIATION_ERROR` | ✅ | 제출 중 상태 불명/대사 불일치 감지 |
| `SUBMITTED` → `PARTIALLY_FILLED` | ✅ | 일부 체결 통지 |
| `SUBMITTED` → `FILLED` | ✅ | 전량 체결 통지 |
| `SUBMITTED` → `CANCEL_PENDING` | ✅ | 취소 요청 |
| `SUBMITTED` → `REJECTED` | ✅ | 브로커 사후 거부 |
| `SUBMITTED` → `RECONCILIATION_ERROR` | ✅ | 대사 불일치 |
| `PARTIALLY_FILLED` → `PARTIALLY_FILLED` | ✅ | 추가 부분 체결(수량 갱신) |
| `PARTIALLY_FILLED` → `FILLED` | ✅ | 잔량 전량 체결 |
| `PARTIALLY_FILLED` → `CANCEL_PENDING` | ✅ | 잔량 취소 요청 |
| `PARTIALLY_FILLED` → `RECONCILIATION_ERROR` | ✅ | 대사 불일치 |
| `CANCEL_PENDING` → `CANCELLED` | ✅ | 취소 확정 |
| `CANCEL_PENDING` → `FILLED` | ✅ | 취소 전에 전량 체결되어 마감 |
| `CANCEL_PENDING` → `PARTIALLY_FILLED` | ✅ | 취소 전에 추가 체결 발생 |
| `CANCEL_PENDING` → `RECONCILIATION_ERROR` | ✅ | 대사 불일치 |

**종결(terminal) 상태:** `RISK_REJECTED`, `FILLED`, `CANCELLED`, `REJECTED`, `RECONCILIATION_ERROR`. 종결 상태에서 나가는 전이는 없다(단, `RECONCILIATION_ERROR`는 운영자 개입·Kill Switch 복구 절차의 대상이며, 자동 흐름에서의 전이는 금지).

**경계 규칙:**
- `APPROVED` 진입은 곧 `ApprovedOrder` 성립을 의미하며, 이는 `RiskDecision == APPROVED`(+ 인간/정책 승인) 없이는 불가능하다(§3.3-b, §4.2).
- `SUBMITTING` 이후의 모든 전이는 **Execution Gateway 전용**이다. Agent Service는 이 영역에 관여하지 못한다(§3).

### 5.3 불법 전이 예외 (Illegal Transition Raises)

- 허용 전이표에 없는 모든 전이 시도는 **예외를 raise** 한다(`_KICKOFF.md` §12: "잘못된 상태 전이는 예외를 발생시켜야 한다", 오버레이 §G: "주문 상태머신(13상태, 불법전이 raise)").
- 예시 불법 전이(전부 raise): `PROPOSED → SUBMITTED`(리스크/승인 우회), `RISK_REJECTED → APPROVED`(거절 뒤집기), `FILLED → SUBMITTING`(종결 후 재제출), `APPROVED → FILLED`(제출 단계 생략), `RECONCILIATION_ERROR → SUBMITTED`(대사 오류 무시).
- **test #9**: 잘못된 주문 상태 전이가 거부되는지 검사. (`_KICKOFF.md` §22)
- 모든 상태 전이(성공/거부 모두)는 Audit Log 기록 대상이다(중요 상태 변경, test #15).

### 5.4 Phase 0/1 구현 범위 (상태 머신)

`_KICKOFF.md` §12·오버레이 §G에 따라 본 Phase에서는 **실제 주문 제출 없이** 상태 머신과 **단위 테스트만** 작성한다. 전이 함수는 mock/메모리 상에서 동작하며, 어떤 실주문도 발생시키지 않는다.

---

## 6. Idempotency Key 규약

### 6.1 원칙

- **모든 주문에는 idempotency key가 있어야 한다**(절대 원칙 §9, `_KICKOFF.md` CLAUDE.md §18 Trading).
- idempotency key의 목적: 네트워크 재시도·버그·Replay로 인한 **동일 주문의 중복 제출을 방지**한다(위협 T3).

### 6.2 키 생성 규칙 (권고 규약)

- 키는 주문 의도를 유일하게 식별하는 결정론적 값으로 생성한다. 구성 요소(권고): `proposal_id` + 종목(symbol) + 매수/매도(side) + 수량 + (가격 또는 주문유형) + 전략 버전(strategy_version) + 의도 발생 시각 윈도.
- 동일한 주문 의도는 동일 키를 만들고, 서로 다른 의도는 서로 다른 키를 만들어야 한다.
- 키는 `OrderProposal` 단계에서 부여되어 `ApprovedOrder` → 브로커 제출까지 **불변(immutable)** 으로 전달된다.

### 6.3 강제 지점 (Enforcement Points)

1. **ApprovedOrder 팩토리:** `idempotency_key` 부재 시 raise. 동일 키의 중복 `ApprovedOrder` 생성 시 raise(§3.3-b). (`_KICKOFF.md` 오버레이 §E: "중복 idempotency_key 거부")
2. **Risk Engine 체크 #17(중복 주문):** 동일 키/동일 의도의 중복 주문을 FAIL 처리(§4.3).
3. **Execution Gateway 제출:** 브로커 제출 시 idempotency key를 전달하고, 동일 키 재제출을 차단한다. 중복 감지는 Kill Switch 트리거(§8 T2)이기도 하다.
4. **test #10**: 동일 idempotency key의 중복 주문을 거부하는지 검사. (`_KICKOFF.md` §22)

### 6.4 중복 감지 시 행동

- 중복이 감지되면 새 주문을 **생성하지 않고** 거부하며, 사건을 `Incident`/Audit Log에 기록한다.
- 중복 주문 감지는 Kill Switch 8 트리거 중 하나다(§8). 단발 거부로 끝나지 않고, 반복·시스템적 중복은 전면 중지로 확대된다.

---

## 7. 잔고 · 체결 대사(Reconciliation) 절차

### 7.1 원칙

- **주문 제출 후 브로커 체결 내역과 내부 장부를 반드시 대사한다**(절대 원칙 §10, `_KICKOFF.md` CLAUDE.md §18: "Every execution must be reconciled with broker data", "Never bypass reconciliation").
- 대사는 선택이 아니라 **의무**다. 대사를 우회하는 어떤 경로도 만들지 않는다.

### 7.2 대사 대상

| 대사 항목 | 내부 장부 | 브로커 측 |
| --- | --- | --- |
| 체결(Execution) | 내부 `Execution` 기록 | `get_executions()` 결과 |
| 포지션(Position) | 내부 `Position` 기록 | `get_positions()` 결과 |
| 잔고(Balance) | 내부 현금/평가 기록 | `get_balance()` 결과 |
| 주문 상태(Order) | 내부 상태 머신(§5) | 브로커 주문 상태 |

브로커 인터페이스 메서드(`_KICKOFF.md` §10): `get_quote`, `get_orderbook`, `get_positions`, `get_balance`, `submit_order(order: ApprovedOrder)`, `cancel_order`, `get_executions`.

### 7.3 대사 절차 (Procedure)

1. **수집:** 제출/체결 이벤트 또는 주기적 스케줄에서 브로커 측 체결·포지션·잔고를 조회한다.
2. **정합 비교:** 내부 장부와 브로커 측 값을 **결정론적으로** 비교한다(수량·가격은 Decimal로, `_KICKOFF.md` 오버레이 §E·ADR-008). 부동소수 비교 금지.
3. **idempotency 정합:** 같은 idempotency key의 주문이 브로커 측에 중복 존재하지 않는지 확인(§6).
4. **불일치 처리:** 수량/금액/상태가 어긋나면 해당 주문을 `RECONCILIATION_ERROR` 상태로 전이(§5.2)하고, `Incident`/Audit Log를 남긴다.
5. **확대:** 대사 불일치는 Kill Switch 트리거(§8 T1)다. 단건 격리에 그치지 않고 전면 중지로 확대하여 추가 피해를 막는다.
6. **차단:** 대사 미일치 상태에서는 Risk Engine 체크 #16(계좌 대사 상태)이 FAIL이 되어 신규 주문이 막힌다. 다중 게이트 G10(대사 정상)도 닫힌다(§2.3).

### 7.4 Phase 0/1 구현 범위 (대사)

본 Phase에서는 **실제 주문·실제 브로커가 없으므로**(§12) 대사는 mock 데이터에 대한 절차·인터페이스·상태(`RECONCILIATION_ERROR`)·연동 규칙으로만 정의·테스트된다. 실 브로커 대사 로직은 후속 Phase에서 구현한다.

---

## 8. Kill Switch: 8 트리거 + 동작 + 복구

### 8.1 개념

Kill Switch는 시스템을 **즉시 안전 상태로 전환**하는 비상 차단 장치다. 비LLM 영역(결정론)에 속한다(`_KICKOFF.md` §3). 상태:

- `ARMED` — 정상 운영(차단 안 됨). 다중 게이트 G6 충족.
- `TRIPPED` — 발동됨. 모든 신규 주문 생성·제출 경로가 닫힘.

### 8.2 8개 트리거 (스펙 §11)

| # | 트리거 | 발동 근거 | 연동 |
| --- | --- | --- | --- |
| 1 | **계좌 대사 불일치** | 내부 장부와 브로커 장부 불일치(§7) | RiskCheck #16, `RECONCILIATION_ERROR` |
| 2 | **중복 주문 감지** | 동일 idempotency key/의도 중복(§6) | RiskCheck #17 |
| 3 | **일일 손실 한도 초과** | 당일 손실이 한도 초과 | RiskCheck #10 |
| 4 | **가격 데이터 지연** | 시장/호가 데이터가 허용 지연 초과 | RiskCheck #4·#5 |
| 5 | **브로커 API 연속 오류** | 브로커 API 연속 실패 | RiskCheck #19 |
| 6 | **비정상 주문 수량** | 수량이 비정상(한도/이상치 초과) | RiskCheck #7·#8 |
| 7 | **전략 버전 불일치** | 실행 전략의 strategy_version이 승인본과 불일치 | 게이트 G9 |
| 8 | **운영자 긴급 중지** | 운영자의 수동 비상 정지(manual) | 운영 절차(§10·§11) |

### 8.3 발동 시 동작 (On Trip)

Kill Switch가 `TRIPPED`되면:

1. **신규 주문 차단:** 모든 신규 `OrderProposal`의 승격(→ `ApprovedOrder`)과 모든 주문 제출(`submit_order`)을 즉시 차단한다. 다중 게이트 G6이 닫힌다(§2.3).
2. **진행 주문 보전 우선:** 진행 중인 주문은 안전을 최우선으로 처리한다(가능 시 신규 위험만 차단하고, 미체결은 운영 절차에 따라 취소/보류). 새로운 리스크를 추가하지 않는 것이 원칙.
3. **모드 강등:** 실행 경로를 사실상 RESEARCH 수준으로 강등(분석은 계속 가능, 자금 행위는 정지).
4. **기록:** 발동 트리거·시각·맥락을 `Incident`와 Audit Log에 남긴다(불변, ADR-006).
5. **통지:** 운영자에게 즉시 통지(RUNBOOK의 장애 대응 절차, `docs/RUNBOOK.md`).

### 8.4 복구 절차 (Recovery)

Kill Switch 복구는 **자동이 아니다.** 다음을 모두 충족해야 `ARMED`로 복귀한다.

1. **근본 원인 규명:** 트리거의 원인을 식별하고 해소(예: 대사 불일치 정정, 데이터 피드 복구, 전략 버전 정합).
2. **대사 일치 확인:** 잔고·체결 대사가 일치 상태로 복원(§7), `RECONCILIATION_ERROR` 잔존 없음.
3. **운영자 승인:** 운영자가 복구를 명시적으로 승인하고, 그 근거·조치를 Audit Log에 기록(§13).
4. **게이트 재확인:** §2.3 다중 게이트(특히 G6·G9·G10)를 재평가하여 전부 통과.

> **안전 비대칭(asymmetry):** 발동은 단일 트리거로 즉시, 복구는 다중 조건+인간 승인으로만. 끄기는 쉽고 켜기는 어렵다.

### 8.5 Phase 0/1 구현 범위 (Kill Switch)

본 Phase는 실거래가 없으므로(§12) Kill Switch는 트리거 정의·상태(`ARMED`/`TRIPPED`)·연동 규칙·복구 절차의 **문서/설계**로 존재한다. 실 발동·실 차단 로직과 실시간 통지는 후속 Phase에서 구현한다.

---

## 9. PAPER / LIVE 분리(자격증명 / 계좌 / 네트워크)

### 9.1 원칙

- **PAPER와 LIVE 환경을 분리한다**(`_KICKOFF.md` §14-14, ADR-005). **운영용 키와 모의투자 키를 분리한다**(§14-13).
- **PAPER와 LIVE 자격증명은 절대 공유하지 않는다**(`_KICKOFF.md` CLAUDE.md §18: "PAPER and LIVE credentials must never be shared").

### 9.2 분리 축 (Separation Axes)

| 축 | PAPER | LIVE | 규칙 |
| --- | --- | --- | --- |
| 자격증명(Credentials) | PAPER 전용 broker 키/토큰 | LIVE 전용 broker 키/토큰 | 서로 다른 비밀 저장소 슬롯. 혼재 금지. |
| 계좌(Account) | 모의투자 계좌번호 | 실계좌 번호 | 코드에서 모드별로 분리 선택. 교차 사용 금지. |
| 환경(Environment) | PAPER 환경(`APP_ENV`/설정 프로필) | LIVE 환경 | 환경별 설정 분리. PAPER 설정으로 LIVE 자격증명 로드 불가, 반대도 불가. |
| 네트워크(Network) | (가능 시) 분리된 네트워크 경계 | (가능 시) 분리된 네트워크 경계 | Agent↔Execution 분리(§3)와 함께 네트워크 수준 격리 가능 구조(§14-10). |
| 게이트 | LIVE 게이트 불필요 | §2.3 G1~G10 전부 충족 필요 | LIVE는 다중 게이트 통과 시에만. |

### 9.3 자격증명 취급

- 브로커 키·계좌번호·비밀번호·토큰을 **코드·로그·프런트엔드·API 응답에 노출하지 않는다**(절대 원칙 §8, `_KICKOFF.md` §14, test #11).
- 웹 클라이언트에 브로커 키를 전달하지 않는다(§14-5).
- `.env`는 Git에 포함하지 않으며 `.env.example`에는 변수명만 둔다(§14-1·2). CI는 `.env`/credential commit 여부를 검사한다(`_KICKOFF.md` §24).
- 관련 변수(`_KICKOFF.md` §14): `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NUMBER`, `KIWOOM_APP_KEY`, `KIWOOM_APP_SECRET` 등. 이들의 PAPER/LIVE 구분 운영은 본 절을 따른다.

### 9.4 Phase 0/1 구현 범위 (PAPER/LIVE)

본 Phase는 실 브로커·실 자격증명이 없다(§12, `_KICKOFF.md` 오버레이 §E). **단, 모의(PAPER) 실행 엔진 자체는 구현되어 있다**(§12.1b, ADR-014): `PaperBrokerAdapter`는 인메모리 모의 브로커로 실 증권사 모의투자 계좌가 아니라 **자체 시뮬레이션 체결**을 생성하며, 실 자격증명을 요구하지 않는다. 따라서 본 Phase의 PAPER는 "실 브로커 모의투자 계좌 연동"이 아니라 "내부 모의체결"(§2.2의 PAPER 정의 중 전자)에 해당한다.

PAPER/LIVE **자격증명·계좌·네트워크 분리**는 여전히 설정 모델·환경 프로필·문서·테스트(비밀 비노출 test #11) 수준으로 정의된다. 실 브로커 모의투자/실계좌 연결은 후속 Phase에서, 본 절 규약을 전제로 구현한다. LIVE 자격증명·실 계좌는 본 Phase에 존재하지 않는다.

---

## 10. GUARDED_LIVE 승인형 실거래 원칙

### 10.1 정의

`GUARDED_LIVE`는 **실계좌 주문 전마다 사용자의 명시적 승인**을 받는 모드다(`_KICKOFF.md` §1). 모든 실주문은 인간 게이트(human-in-the-loop)를 통과한다.

### 10.2 흐름과 불변식

```
OrderProposal(PROPOSED)
  → Risk Engine 평가
    → REJECTED 이면 RISK_REJECTED (종결)
    → APPROVED 이면 RISK_APPROVED
       → AWAITING_HUMAN  (사용자 승인 대기)
          → 사용자 명시 승인 → APPROVED → SUBMITTING → ...
          → 사용자 거부/철회 → CANCELLED (종결)
```

**불변식:**
1. **Risk Engine 선행:** 사용자 승인 화면에 오르기 전에 반드시 Risk Engine `APPROVED`여야 한다(§4). Risk Engine이 거절한 주문은 사용자에게 승인 요청으로 제시되지 않는다.
2. **명시적 승인:** 승인은 능동적·명시적이어야 한다. 기본 동작이 "승인"이 되는 UI/자동 클릭/타임아웃 자동승인은 금지. 무응답·타임아웃은 **승인 아님(= 미실행)** 으로 처리한다.
3. **승인의 범위:** 사용자 승인은 그 **특정 주문 1건**에 한정된다. 1회 승인으로 다수 주문을 일괄 자동화하지 않는다(그것은 AUTO_LIVE 영역, §11).
4. **승인 기록:** 누가·언제·무엇을 승인했는지 Audit Log에 남긴다(§13, test #15).
5. **게이트 동시 충족:** §2.3 다중 게이트(G1~G2, G4~G10)와 Kill Switch ARMED(G6)가 함께 충족돼야 실제 제출된다.

### 10.3 UI 안전 규약

- Phase 1 `/risk` 화면 등에는 **실제 주문 버튼을 만들지 않는다**(`_KICKOFF.md` §21: "실제 주문 버튼은 만들지 않는다"). 본 Phase에서 GUARDED_LIVE 승인 UI는 구현 대상이 아니다.
- mock 데이터를 실데이터처럼 표시하지 않는다(배너 의무).

---

## 11. AUTO_LIVE 활성화 조건(사전승인 전략 · 한도)

### 11.1 정의

`AUTO_LIVE`는 **사전 승인된 전략과 한도 내에서만 자동 주문**하는 모드다(`_KICKOFF.md` §1). 인간이 매 주문을 승인하지 않는 대신, **사전에** 전략·한도·조건을 엄격히 승인하고 그 경계 안에서만 자동화한다.

### 11.2 활성화 선행조건 (Preconditions, 전부 AND)

| 조건 | 내용 |
| --- | --- |
| 모드/플래그 | `TRADING_MODE=AUTO_LIVE` **그리고** `LIVE_TRADING_ENABLED=true` **그리고** `AUTO_EXECUTION_ENABLED=true`(게이트 G1~G3) |
| 사전승인 전략 | 실행 전략이 **명시적으로 사전 승인**되고, Risk Engine 체크 #2(허용 전략)에 등록됨 |
| 전략 버전 고정 | 실행 전략의 `strategy_version`이 사전 승인된 버전과 **일치**(게이트 G9, Kill Switch T7). 모든 전략 변경은 새 버전 생성(`_KICKOFF.md` CLAUDE.md §18) → 재승인 필요 |
| 사전승인 한도 | `config/risk_limits.yml`의 한도(주문금액·포지션·총노출·일일손실·낙폭·거래횟수·슬리피지 등)가 AUTO_LIVE용으로 승인됨(§13) |
| 허용 종목 | 거래 종목이 화이트리스트에 등록(체크 #1) |
| 대사 정상 | 직전 대사 일치, `RECONCILIATION_ERROR` 없음(게이트 G10, §7) |
| Kill Switch ARMED | 전역 Kill Switch 정상(게이트 G6, §8) |
| 백테스트/검증 통과 | 전환 전 검증사항 충족(`docs/RUNBOOK.md`: 모의→실거래 전환 전 검증) |

### 11.3 자동 실행 중 불변식

1. **모든 자동 주문도 Risk Engine 22 체크를 통과**해야 한다(§4). AUTO_LIVE라고 해서 리스크 검증을 건너뛰지 않는다. 자동화는 "인간 승인"만 정책 승인으로 대체할 뿐, 결정론적 리스크 게이트는 그대로다.
2. **한도 위반 즉시 차단:** 일일 손실·낙폭·거래횟수 등 한도에 도달하면 해당 체크가 FAIL → 자동 주문 정지. 필요 시 Kill Switch 발동(§8).
3. **전략 버전 드리프트 금지:** 실행 중 전략 코드가 바뀌면 버전 불일치 → Kill Switch T7.
4. **운영자 긴급 중지 상시 가능:** 운영자는 언제든 수동으로 전면 중지할 수 있다(Kill Switch T8).
5. **상태 머신 준수:** `RISK_APPROVED → APPROVED`(정책 자동 승인) 전이는 사전승인 정책 범위 내에서만(§5.2).

### 11.4 Phase 0/1 구현 범위 (AUTO_LIVE)

본 Phase에서 AUTO_LIVE는 **구현·활성화하지 않는다**(§12, `_KICKOFF.md` §1: "실거래 기능은 명시적인 별도 요청 전까지 구현하거나 활성화하지 않는다"). 본 절은 후속 Phase에서 충족해야 할 **활성화 조건의 규범**으로만 존재한다. 기본 플래그는 `false`다(§2.1).

---

## 12. Phase 0/1 현재 구현 범위와 명시적 비구현

### 12.1 현재 구현 범위 (In Scope)

`_KICKOFF.md` §11·§12·오버레이 §E·§G에 근거한다. 본 Phase에서 안전 관련으로 구현하는 것:

| 구현 항목 | 비고 |
| --- | --- |
| 기본값 `TRADING_MODE=RESEARCH`, `LIVE_TRADING_ENABLED=false`, `AUTO_EXECUTION_ENABLED=false` | 설정·`.env.example`·test #6/#7 |
| `RiskEngine` 인터페이스 + **deny-by-default** + 최소 규칙 | test #5(미등록 종목 거절) |
| `RiskDecision` 모델 | Risk Engine만 생성 |
| `config/risk_limits.yml` 초안 | 한도 변경은 ADR/로그(§13) |
| `ApprovedOrder` 팩토리(APPROVED RiskDecision 없으면 raise, 중복 idempotency_key 거부) | test #4 |
| 주문 상태 머신(13상태) + 허용 전이 + **불법 전이 raise** + 단위 테스트 | test #9 |
| Agent↔Execution **import 격리** + 서비스 분리 구조 | test #8(소스/AST 스캔 + import 단언) |
| `BrokerAdapter` Protocol + `MockBrokerAdapter`(안전 stub) | 실주문 없음 |
| **PAPER(모의) 실행 경로**: `PaperBrokerAdapter` + `TradingService` + `orders`/`fills`/`positions` 테이블 | **구현됨·안전**(§12.1b). `TRADING_MODE=PAPER`에서만. 실돈·실브로커 없음 |
| **실 시세 데이터**(keyless Yahoo Finance + mock 폴백) | 가격은 실데이터; provider는 never-raise(ADR-013). mock은 항상 라벨링 |
| **실 LLM 에이전트**(Anthropic, mock 폴백) | `AGENT_RUNTIME=llm` + `ANTHROPIC_API_KEY`. 에이전트는 여전히 주문 권한 없음(ADR-015) |
| idempotency key 규약(부여·불변·중복 거부) | test #10 |
| 비밀값 비노출(코드·로그·API) | test #11 |

### 12.1b PAPER(모의) 실행은 구현되었고 안전하다

> **요지:** PAPER 실행은 **구현되었으며 안전하다**(실제 돈을 움직이지 않고, 실제 브로커에 접속하지 않는다). LIVE(`GUARDED_LIVE`/`AUTO_LIVE`, 실 브로커) 실행은 **여전히 의도적으로 비구현**이며 다중 게이트 뒤에 잠겨 있다(§12.2). 두 모듈 수준 플래그가 이 사실을 코드로 못박는다: `PAPER_EXECUTION_IMPLEMENTED = True`, `LIVE_EXECUTION_IMPLEMENTED = False`(`src/kospi_watcher/config.py`).

**무엇이 안전한가 (왜 PAPER가 실거래가 아닌가):**

1. **실돈 없음·실브로커 없음.** `PaperBrokerAdapter`(`domain/execution/paper.py`, `mode="PAPER"`)는 인메모리 모의 브로커다. 어떤 실 증권사 API도 호출하지 않으며, 체결은 전부 **시뮬레이션**이다. 배너: `PAPER BROKER — SIMULATED FILLS, NO REAL ORDERS, NO REAL MONEY`.
2. **체결은 시뮬레이션이다.** `simulate_fill(order, reference_price)`는 LIMIT 주문은 지정가로, MARKET 주문은 기준가로 **전량 모의 체결**한다(기준가 없는 MARKET은 `PaperFillError`). 이는 실제 시장 체결이 아니라 결정론적 모의 체결이다.
3. **단일 모드 게이트.** 실행은 **오직 `TRADING_MODE=PAPER`에서만** 일어난다. `TradingService.submit_order`는 그 외 모드에서 `ExecutionDisabledError`를 던지고, API는 **HTTP 409**로 거절한다(`RESEARCH`는 분석 전용으로 주문을 거부한다). 즉 기본값 `RESEARCH`에서는 PAPER 체결조차 생성되지 않는다.
4. **안전 불변식 그대로 유지.** PAPER 경로도 §4의 **deterministic deny-by-default Risk Engine을 선행 통과**해야 한다. `RiskDecision == APPROVED`일 때만 `ApprovedOrder.from_decision`으로 승격되고(§3.3-b), 주문은 13상태 머신(§5)을 따라 전이하며 각 전이는 영속화·Audit Log(`ORDER_STATE_TRANSITION`)에 기록된다. 손익은 순수 `Decimal` 계산(`position.py`, ADR-008)이고, idempotency 중복은 거부된다(§6).
5. **게이트웨이 게이팅.** `ExecutionGateway.submit`은 시뮬레이션 브로커(`MOCK`/`PAPER`)만 허용한다(PAPER는 추가로 `PAPER_EXECUTION_IMPLEMENTED` 필요). 비시뮬레이션(=실/LIVE) 브로커는 `LIVE_EXECUTION_IMPLEMENTED and live_execution_armed`가 모두 참이 아닌 한 `GatewayBlockedError`로 차단되며, 본 Phase에서 둘 다 거짓이다.

상세 설계·근거는 **ADR-014(PAPER 실행)**, 데이터 모델은 DATA_DICTIONARY §2.6~2.8(`orders`/`fills`/`positions`)와 §4.10~4.11(`Fill`/`PositionState`), 흐름은 ARCHITECTURE §4b를 참조한다.

### 12.2 명시적 비구현 (Explicitly Out of Scope — NO LIVE TRADING)

> 아래는 본 Phase에서 **의도적으로 구현하지 않는다.** "아직 안 한 것"이 아니라 "지금 하면 안 되는 것"이다. `_KICKOFF.md` §1·§5·§10·§11·§23, 오버레이 §E. (참고: **모의(PAPER) 실행과 실 시세·실 LLM은 구현되었다** — §12.1b. 아래는 그와 별개로 **실거래(LIVE)** 영역만 비구현임을 규정한다.)

| 비구현 항목 | 근거 |
| --- | --- |
| **실거래(LIVE) / 실주문 / 실 브로커 연결** | 실주문 코드 없음. `LIVE_EXECUTION_IMPLEMENTED=False`. (모의 PAPER 체결은 구현됨이나 실브로커·실돈 아님, §12.1b)(`_KICKOFF.md` 오버레이 §E·§C) |
| **실 증권사 API**(한국투자증권 KIS, 키움 Kiwoom) 연동 | "실제 KIS/Kiwoom API 연결은 구현하지 않는다"(§10). KIS/Kiwoom 등 브로커·공시·거시 피드는 `/system/status`에서 `not_configured` placeholder |
| **`execution-gateway`의 실주문 기능** | 실주문 없이 실행됨. 게이트웨이는 시뮬레이션 브로커(MOCK/PAPER)만 허용, LIVE 브로커는 차단(§12.1b·§5·§23) |
| **실 Anthropic API 기반 자금/주문 결정** | LLM 에이전트는 실 Anthropic 호출이 가능하나(§12.1b, ADR-015) **여전히 분석 전용**이며 주문 권한이 없다. 자금 결정은 결정론적 코드만(§3) |
| **GUARDED_LIVE 승인 UI / 실제 주문 버튼** | `/risk`에 실주문 버튼 금지(§21) |
| **AUTO_LIVE 자동매매 로직** | 별도 요청 전까지 구현·활성화 금지(§1) |
| **22 체크 전부의 완전한 실로직 / 실 Kill Switch 발동 / 실 대사 로직** | 인터페이스·모델·deny-by-default·최소 규칙·설계만(§11) |
| **실 자격증명 / 실 계좌 / 실 네트워크 분리 운영** | 설정·문서·테스트 수준(§9) |

### 12.3 정직성 (mock 라벨링 · 시뮬레이션 명시)

- **실데이터/모의데이터 구분.** 시세(KOSPI/USDKRW/ETF)는 실데이터(Yahoo, keyless)이며 `source="yahoo"`로 표기된다. 폴백·오프라인 mock은 `source="mock"`·`stale=True`로 **항상 라벨링**되어 실데이터로 오인될 수 없다(ADR-013). mock 에이전트 출력도 MOCK 배너로 표기한다(`"MOCK DATA — NOT REAL MARKET DATA"`)(`_KICKOFF.md` 오버레이 §E, §21).
- **PAPER 체결은 시뮬레이션임을 명시.** 모든 PAPER 체결(`fills.liquidity="PAPER"`)과 브로커 ack(`PAPER-…`)는 모의이며, 배너 `PAPER BROKER — SIMULATED FILLS, NO REAL ORDERS, NO REAL MONEY`로 실주문/실돈이 아님을 못박는다(§12.1b).
- 미검증 항목(예: Docker 미설치로 `docker compose up` 미검증)은 통과한 것처럼 보고하지 않는다(`_KICKOFF.md` 오버레이 §C).

---

## 13. 변경 통제(리스크 한도 변경 시 ADR / 감사 로그)

### 13.1 원칙

- **리스크 변경 시 ADR 또는 변경 로그가 필요하다**(`_KICKOFF.md` §11). **실거래 관련 설정 변경은 별도 감사 로그 대상이다**(`_KICKOFF.md` §14-12). **운영 트레이딩 설정을 임의 변경하지 않는다**(CLAUDE.md §18: "Never modify production trading settings").
- **테스트를 통과시키기 위해 리스크 통제를 약화하지 않는다**(`_KICKOFF.md` §2-18). 변경 통제는 안전을 **약화하는 방향의 변경**을 특히 엄격히 다룬다.

### 13.2 변경 통제 대상 (Change-Controlled Artifacts)

| 대상 | 위치 / 식별 | 변경 시 요구 |
| --- | --- | --- |
| 리스크 한도값 | `config/risk_limits.yml` | ADR 또는 변경 로그 + Audit Log + 버전/해시 갱신 |
| 허용 종목 화이트리스트 | `config/instruments.yml` 등 | 변경 로그 + Audit Log |
| 허용 전략 목록 / 전략 버전 | strategy version 레지스트리 | 새 버전 생성 + (AUTO_LIVE 시) 재승인 |
| 운용 모드 / 실거래 플래그 | `TRADING_MODE`, `LIVE_TRADING_ENABLED`, `AUTO_EXECUTION_ENABLED` | **실거래 설정 변경 = 별도 감사 로그 의무**(§14-12) |
| Risk Engine 규칙/임계 | Risk Engine 코드 + 한도 | ADR(중대 변경) + 테스트 + Audit Log |
| Kill Switch 트리거/임계 | Kill Switch 설정 | ADR 또는 변경 로그 + Audit Log |
| 본 문서(TRADING_SAFETY.md) | `docs/TRADING_SAFETY.md` | 변경은 ADR로 정당화, 안전 약화 변경은 특별 검토 |

### 13.3 변경 절차

1. **제안:** 변경 사유·영향·리스크를 기술한다. 안전을 약화하는 변경이면 그 정당성을 명시적으로 입증한다.
2. **기록:** 중대 결정은 ADR(`docs/adr/`, 형식: Status / Context / Decision / Consequences / Alternatives Considered, `_KICKOFF.md` §17)로 남긴다. 한도/설정 조정은 최소 변경 로그를 남긴다. 관련 ADR: **ADR-010**(deny-by-default Risk Engine).
3. **감사 로그:** 변경 사실(누가·언제·무엇을·이전값→새값)을 **Audit Log**에 남긴다. Audit Log는 일반 애플리케이션 흐름에서 **임의 삭제 불가**(`_KICKOFF.md` §14-11, ADR-006 불변성). **test #15**: Audit Log가 중요 상태 변경을 기록하는지 검사.
4. **검증:** 변경 후 관련 테스트(리스크·상태머신·경계)를 재실행하여 안전 불변식이 유지됨을 확인한다.
5. **버전 식별:** `risk_limits.yml` 등은 변경 시 버전/해시를 갱신하고, `RiskDecision.risk_limits_version`에 기록되어 어떤 한도로 평가했는지 추적 가능해야 한다.

### 13.4 안전 약화 변경에 대한 특별 규칙

- 리스크 한도 완화, 게이트 제거, deny-by-default 예외, 불법 전이 허용, Kill Switch 트리거 비활성화 등 **안전을 약화하는 변경**은 본 문서에서 기본적으로 금지된다.
- 그런 변경이 불가피하다면, 사용자의 명시적 요청 + ADR + Audit Log + 테스트 갱신을 **모두** 거쳐야 한다. "임시"·"테스트 통과용"·"잠깐만"이라는 이유로는 절대 허용하지 않는다.

---

## 부록 A. 안전 불변식 빠른 점검표 (Invariants Checklist)

- [ ] 기본값: `TRADING_MODE=RESEARCH`, `LIVE_TRADING_ENABLED=false`, `AUTO_EXECUTION_ENABLED=false` (test #6, #7)
- [ ] 단일 환경변수로 LIVE 불가 — 다중 게이트 G1~G10 전부 충족 시에만 LIVE (§2)
- [ ] LLM은 분석/`OrderProposal`만, 주문 API 직접 호출 불가 (§3)
- [ ] `submit_order`는 `domain/execution/broker` + `apps/execution-gateway`에만 존재; agent 측 import 경로 없음 (§3, test #8)
- [ ] `ApprovedOrder`는 APPROVED `RiskDecision` 없이 생성 불가(팩토리 raise), 중복 idempotency_key 거부 (§3, §6, test #4, #10)
- [ ] Risk Engine은 LLM 미사용, deny-by-default, 22 체크 (§4, test #5)
- [ ] 상태 머신 13상태, 허용 전이만, 불법 전이 raise (§5, test #9)
- [ ] 모든 주문에 idempotency key (§6)
- [ ] 체결/잔고 대사 의무, 불일치 시 `RECONCILIATION_ERROR` + Kill Switch (§7, §8)
- [ ] Kill Switch 8 트리거, 발동은 즉시·복구는 인간 승인 (§8)
- [ ] PAPER/LIVE 자격증명·계좌·환경·네트워크 분리, 비밀 비노출 (§9, test #11)
- [ ] 리스크 한도/실거래 설정 변경은 ADR/변경 로그 + Audit Log (§13, test #15)
- [ ] Phase 0/1: 실거래·실주문·실 브로커·실 데이터 없음(전부 mock) (§12)

## 부록 B. 관련 테스트 매핑 (`_KICKOFF.md` §22)

| 테스트 | 안전 절 |
| --- | --- |
| #4 OrderProposal이 RiskDecision 없이 ApprovedOrder가 될 수 없음 | §3.3-b, §4.2 |
| #5 deny-by-default Risk Engine이 미등록 종목 거절 | §4.4 |
| #6 LIVE_TRADING_ENABLED 기본 false | §2.1 |
| #7 AUTO_EXECUTION_ENABLED 기본 false | §2.1 |
| #8 Agent Service가 BrokerAdapter.submit_order 접근 불가 | §3.3-d |
| #9 잘못된 주문 상태 전이 거부 | §5.3 |
| #10 동일 idempotency key 중복 주문 거부 | §6.3 |
| #11 비밀값이 API 응답·로그에서 비노출 | §3.6, §9.3 |
| #15 Audit Log가 중요 상태 변경 기록 | §10.2, §13.3 |

---

*본 문서는 KOSPI-WATCHER 안전 캐논의 일부다. 본 문서를 약화시키는 변경은 §13의 변경 통제 절차 없이 이루어질 수 없다. 안전이 의심스러우면, 항상 더 보수적인 해석을 택한다.*
