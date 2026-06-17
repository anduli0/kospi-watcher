# KOSPI-WATCHER — Product Spec (Phase 0)

> 본 문서는 KOSPI-WATCHER의 제품 사양(Product Specification)이다.
> 권위 있는 출처는 `_KICKOFF.md`((A) 확정 결정 오버레이 + (B) 원본 스펙 전문)이며, 본 문서의 모든 내용은 이와 일치한다.
> 충돌 시 `_KICKOFF.md` (A) 오버레이가 우선한다.
>
> **상태(Status):** Phase 0 / Draft
> **범위(Scope):** 이번 빌드는 **Phase 0 + Phase 1만** 다룬다. 전부 mock이며 **실거래는 없다.**
> **마지막 갱신 기준일:** 2026-06-17

---

## 0. 한눈에 보기 (Executive Summary)

KOSPI-WATCHER는 한국 증시(KOSPI / KOSPI200 / KOSDAQ)의 가격·수급·거시경제·국내외 정세·뉴스·공시·섹터·종목·구조적 성장 산업을 **하나의 웹사이트에서 분석**하고, 향후 증권사 계좌와 연결하여 KOSPI 또는 KOSPI200 연계 ETF의 **모의매매**와 **리스크 통제형 자동매매**를 수행하는 시스템이다.

핵심 설계 원칙은 **"LLM은 분석만, 주문은 deterministic 코드만"** 이다. LLM 에이전트는 시장 분석 결과와 Trade Proposal만 생성하며, 모든 주문은 LLM 없이 순수 코드로 구현된 deterministic Risk Engine의 deny-by-default 승인을 거친 뒤 격리된 Execution Gateway를 통해서만 처리된다.

| 항목 | 값 |
|---|---|
| 기본 운용 모드 | `TRADING_MODE=RESEARCH` |
| 실거래 활성화 | `LIVE_TRADING_ENABLED=false` (기본) |
| 자동 실행 활성화 | `AUTO_EXECUTION_ENABLED=false` (기본) |
| 이번 빌드 범위 | Phase 0(설계·정책 문서) + Phase 1(기반 구현) |
| 데이터 | 전부 mock. 실시장 데이터 없음, 실거래 없음 |
| 아키텍처(로컬) | 무도커 로컬모드 — SQLite(aiosqlite) + fakeredis 폴백 |

---

## 1. 제품 목표 · 비전 (Product Goals & Vision)

### 1.1 비전

> 한국 증시를 **하나의 화면에서 분석**하고, 사람이 통제권을 쥔 채로 **리스크가 사전에 검증된 트레이딩 리서치**까지 이어지는 시스템.

KOSPI-WATCHER는 분산된 정보(지수·수급·거시·정세·뉴스·공시·섹터·종목·산업)를 통합 분석하고, 그 분석을 **검증 가능하고 안전한 방식**으로 트레이딩 의사결정 보조까지 연결하는 것을 지향한다. 단, **안전(Safety)이 기능(Feature)보다 항상 우선**한다.

### 1.2 시스템의 최종 목표 (16기능)

최종 시스템은 다음 16기능을 제공하는 것을 목표로 한다. (Phase 0/1 범위는 §8 참조.)

1. KOSPI, KOSPI200, KOSDAQ 및 주요 시장지표 분석
2. 외국인·기관·개인 수급 분석
3. 프로그램 매매, 선물·옵션, 공매도 및 변동성 분석
4. 국내외 거시경제 지표 분석
5. 환율, 금리, 원자재, 글로벌 증시 분석
6. 국내외 주요 뉴스와 국제정세 분석
7. DART 공시 및 기업 이벤트 분석
8. 주요 섹터와 종목 분석
9. 현재 시장을 주도하는 산업과 테마 분석
10. 장기적으로 성장 가능성이 큰 산업 탐색
11. 시장 국면 분류 (Market Regime Classification)
12. 지수 상승·하락 확률 및 정량 신호(quant signal) 산출
13. 전략 백테스트 (Backtest)
14. 모의매매 (Paper Trading)
15. 사용자 승인형 실거래 (Guarded Live Trading)
16. 엄격한 리스크 통제 하의 제한적 자동매매 (Constrained Auto Trading)

### 1.3 제품 원칙 (Product Principles)

- **분석과 실행의 분리:** LLM 영역(분석·근거·Trade Proposal)과 비LLM 영역(가격/수량 계산·리스크 검증·주문 승인·제출·대사·Kill Switch)을 엄격히 분리한다.
- **Deny-by-default:** 명시적으로 승인되지 않은 주문은 모두 거절한다.
- **Point-in-time 정직성:** 미래 데이터가 과거 백테스트로 유입되지 않게 한다. `available_at` 이후에만 데이터를 전략에서 사용한다.
- **Mock은 mock으로:** 가짜 금융 데이터를 실제 데이터처럼 표시하지 않는다(화면에 `MOCK DATA — NOT REAL MARKET DATA` 배너).
- **추측 금지:** 공식 API 명세가 불확실하면 추측하여 구현하지 않는다.
- **비밀값 비노출:** API 키·계좌번호·비밀번호·토큰을 코드·로그·프런트엔드에 노출하지 않는다.

---

## 2. 문제 정의 (Problem Statement)

### 2.1 사용자가 겪는 문제

한국 증시를 진지하게 분석·매매하려는 사용자는 다음 문제에 직면한다.

| # | 문제 | 설명 |
|---|---|---|
| P1 | **정보 파편화** | 지수·수급·프로그램·선물옵션·공매도·거시·환율·금리·원자재·글로벌·뉴스·정세·DART 공시·섹터·종목 정보가 서로 다른 사이트/단말에 흩어져 있다. |
| P2 | **시점 왜곡(look-ahead bias)** | 백테스트/신호 산출 시 "그 시점에 알 수 있었던 정보"와 "사후에 알게 된 정보"가 뒤섞여 전략 성과가 과대평가된다. |
| P3 | **근거 없는 주장의 혼입** | 뉴스·SNS의 미확인 정보가 출처 검증 없이 판단에 반영된다. |
| P4 | **시장 국면 인식 부재** | 동일한 신호라도 RISK_ON / RISK_OFF / CRISIS 등 국면에 따라 의미가 달라지는데 이를 체계적으로 분류하지 못한다. |
| P5 | **자동매매의 안전성 공백** | 알고리즘/LLM 기반 매매가 폭주(runaway)하거나 중복 주문·미대사·한도 초과로 통제 불능에 빠질 위험이 크다. |
| P6 | **비밀값/실거래 위험** | 실거래 API 키·계좌 정보가 코드/로그/프런트로 유출되거나, 환경변수 하나로 실거래가 켜지는 사고가 발생할 수 있다. |

### 2.2 KOSPI-WATCHER의 해법 방향

- **P1 →** 10메뉴 통합 정보구조 + 21에이전트 분석 + Chief Market Synthesizer 종합(§6, §1.2).
- **P2 →** `event_time / published_at / available_at / ingested_at` 4시점 보존 + point-in-time 백테스트.
- **P3 →** Evidence에 `source_id` 필수, **출처가 없는 주장은 최종 점수에 반영하지 않음**(원칙 문서화).
- **P4 →** 9개 시장 국면(Market Regime) 분류 엔진.
- **P5 →** deterministic Risk Engine(deny-by-default) 선행 승인 + 주문 상태 머신(불법 전이 raise) + idempotency + 체결/잔고 대사 + Kill Switch.
- **P6 →** Agent ↔ Execution 서비스 격리, 비밀값 비노출, 다중 플래그(`TRADING_MODE` / `LIVE_TRADING_ENABLED` / `AUTO_EXECUTION_ENABLED`)로 단일 변수 실거래 활성화 차단.

---

## 3. 주요 사용자 / 페르소나 (Users & Personas)

| 페르소나 | 코드 | 1차 관심사 | 핵심 메뉴(최종) | Phase 0/1 접점 |
|---|---|---|---|---|
| 개인 액티브 투자자 | **P-INV** | 오늘의 시장, 국면, 섹터/종목 논거, 모의매매 | 1·2·5·6·8·9 | `/`, `/dashboard`, `/agents` |
| 리서치 운용 담당 | **P-RES** | 거시·정세·수급·기술적 분석, 전략/백테스트, 에이전트 근거·반대근거 | 3·4·7·8 | `/agents`, `/risk` |
| 리스크 / 컴플라이언스 관리자 | **P-RISK** | 리스크 한도, deny-by-default, Audit Log, Kill Switch, 안전장치 | 9·10 | `/risk`, `/system`, `/api/v1/audit-logs` |

### 3.1 페르소나 상세

#### P-INV — 개인 액티브 투자자
- **목표:** "오늘 시장이 어떤 국면인지, 어떤 섹터/종목이 주도하는지 빠르게 파악하고, 실제 돈을 걸기 전에 모의로 검증하고 싶다."
- **니즈:** 직관적 대시보드, 국면 한눈에 보기, 종목별 상승/하락 논거와 **무효화 조건(invalidation)**, PAPER 모드 모의체결.
- **고통:** 정보 과부하, 근거 없는 종목 추천, 실거래 사고 공포.

#### P-RES — 리서치 운용 담당
- **목표:** "분석의 근거와 반대 근거를 추적하고, 전략을 point-in-time으로 백테스트해 신뢰할 만한 신호를 얻고 싶다."
- **니즈:** 에이전트별 `thesis / evidence / counterevidence / confidence / impact`, 출처(`source_id`) 추적, 전략 버전 관리, 워크포워드 검증.
- **고통:** look-ahead bias, 재현 불가능한 분석, 출처 불명 데이터.

#### P-RISK — 리스크 / 컴플라이언스 관리자
- **목표:** "어떤 LLM도 실주문을 낼 수 없고, 모든 주문이 사전 한도 검증을 거치며, 모든 상태 변경이 감사되도록 보장하고 싶다."
- **니즈:** deny-by-default 가시화, 리스크 한도(`risk_limits.yml`) 관리, 불변 Audit Log, Kill Switch, 실거래 설정 변경의 별도 감사.
- **고통:** 통제되지 않는 자동매매, 비밀값 유출, 한도 우회.

> **운영 원칙:** 운영 환경에서 Claude Code 또는 LLM은 실계좌 주문 권한을 갖지 않으며, production secret을 읽거나 출력할 수 없다(문서화된 운영 원칙). 따라서 "Claude Code/LLM"은 **운영자(operator) 도구**이지 의사결정 주체가 아니다.

---

## 4. 핵심 사용 시나리오 (User Stories)

> 형식: **As a** [페르소나] **, I want** [행동] **, so that** [가치].
> 각 시나리오에는 안전 불변식(Safety Invariant)을 함께 명시한다.
> ※ 아래 PAPER / GUARDED_LIVE 흐름은 **최종 제품의 목표 흐름**이며, 이번 빌드(Phase 0/1)에서는 **mock 인터페이스·상태 머신·검증까지만** 구현된다(실체결·실주문 없음).

### US-1 (RESEARCH — 기본 흐름) · P-INV / P-RES
- **As a** 개인 액티브 투자자 / 리서치 담당,
- **I want** 오늘의 시장 국면과 주도 섹터·종목 분석을 근거와 함께 조회하기를,
- **so that** 주문을 내지 않고도 시장을 이해하고 의사결정을 준비할 수 있다.
- **흐름:** `/` 진입 → 현재 `TRADING_MODE=RESEARCH` 및 `LIVE TRADING DISABLED` 확인 → `/agents`에서 mock agent 목록·스키마·`POST /api/v1/agents/mock-run` 결과(AgentFinding) 확인 → `thesis / evidence(source_id) / counterevidence / confidence / impact`로 근거 검토.
- **Safety Invariant:** RESEARCH 모드에서는 **주문을 일절 생성하지 않는다.** mock 데이터는 `MOCK DATA` 배너로 표기된다.

### US-2 (PAPER — 모의체결 흐름) · P-INV
- **As a** 개인 액티브 투자자,
- **I want** 분석으로 도출된 아이디어를 모의로 체결해 보기를,
- **so that** 실제 자금 위험 없이 전략을 검증할 수 있다.
- **목표 흐름:** 전략/신호 → OrderProposal 생성 → `POST /api/v1/order-proposals/validate`(스키마 검증) → `POST /api/v1/risk/evaluate`(deny-by-default Risk Engine) → 승인 시 **내부 모의체결 또는 증권사 모의투자 계좌**에서 체결 → 모의 손익/포지션 반영.
- **Safety Invariant:** 실거래 없음. PAPER와 LIVE 자격증명/환경은 분리된다. 모든 OrderProposal은 `RiskDecision` 없이 `ApprovedOrder`가 될 수 없다.

### US-3 (GUARDED_LIVE — 주문 전 사용자 승인 흐름) · P-INV / P-RISK
- **As a** (향후) 실계좌 사용자이자 리스크 관리자,
- **I want** 실계좌 주문이 나가기 전에 매 건 명시적으로 승인하기를,
- **so that** 사람이 항상 최종 통제권을 쥔 채로만 실거래가 일어난다.
- **목표 흐름:** OrderProposal → Risk Engine 승인(`RISK_APPROVED`) → `AWAITING_HUMAN`(사용자 명시 승인 대기) → 사용자 승인 → `APPROVED` → Execution Gateway가 `submit_order(ApprovedOrder)` → `SUBMITTED` → 체결 → **체결/잔고 대사** → Audit Log 기록.
- **Safety Invariant:** **이번 빌드에서는 실행하지 않는다.** `LIVE_TRADING_ENABLED=false`가 유지된다. LLM/Agent Service는 `BrokerAdapter.submit_order()`에 접근 불가(구조적 격리 + 테스트로 강제). 모든 주문은 idempotency key를 가진다.

### US-4 (AUTO_LIVE — 제한적 자동매매) · P-RISK
- **As a** 리스크 관리자,
- **I want** 사전 승인된 전략과 한도 내에서만 자동 주문이 일어나도록,
- **so that** 자동화의 이점을 취하되 폭주를 구조적으로 차단할 수 있다.
- **목표 흐름:** 사전 승인된 StrategyVersion + RiskLimit → 신호 발생 → Risk Engine(한도/대사/변동성/중복 등) 통과 시에만 정책 승인 → Execution Gateway 제출 → 대사 → 이상 시 **Kill Switch** 작동.
- **Safety Invariant:** **이번 빌드에서는 비활성화.** `AUTO_EXECUTION_ENABLED=false`. 한도·전략은 사전 승인 대상이며, 리스크 통제를 테스트 통과 목적으로 약화하지 않는다.

### US-5 (리스크 검증) · P-RISK
- **As a** 리스크 관리자,
- **I want** 임의의 테스트 Proposal을 입력해 Risk Engine의 승인/거절을 즉시 확인하기를,
- **so that** deny-by-default가 실제로 동작함을 검증할 수 있다.
- **흐름:** `/risk` 화면 → 테스트 Proposal 입력 → `POST /api/v1/risk/evaluate` → 미등록 종목/미승인 전략은 거절(`RISK_REJECTED`) 확인. **실제 주문 버튼은 존재하지 않는다.**

### US-6 (감사·관측) · P-RISK
- **As a** 컴플라이언스 관리자,
- **I want** 중요 상태 변경이 Audit Log에 남고 페이지네이션으로 조회되기를,
- **so that** 사후 추적과 규정 준수를 보장할 수 있다.
- **흐름:** `GET /api/v1/audit-logs`(pagination, 민감정보 제외) → `/system`에서 API/DB/Redis 상태·버전·환경·trading mode·LIVE disabled 확인.

### US-7 (시스템 상태 점검) · P-INV / P-RES / P-RISK
- **As a** 모든 사용자,
- **I want** 시스템과 데이터 소스의 상태를 한눈에 보기를,
- **so that** 분석 결과를 신뢰할 수 있는지 판단할 수 있다.
- **흐름:** `GET /health` / `GET /api/v1/system/status` → 서비스 버전·환경·서버 시각·trading mode·기능 플래그·데이터 소스 상태 placeholder 확인. (비밀값은 절대 반환되지 않는다.)

---

## 5. 운용 모드 4종 상세 (Operating Modes)

시스템 운용 모드는 4종이며, 기본값은 **RESEARCH**이다.

| 모드 | 주문 생성 | 체결 대상 | 사람 승인 | 자동 주문 | 이번 빌드(Phase 0/1) |
|---|---|---|---|---|---|
| **RESEARCH** | ✗ (생성 안 함) | 없음 | 해당 없음 | ✗ | **기본값.** 분석만, 주문 미생성 |
| **PAPER** | ✓ (Proposal) | 내부 모의체결 / 증권사 모의투자 계좌 | 해당 없음 | ✗ | mock 인터페이스·검증까지만 |
| **GUARDED_LIVE** | ✓ (Proposal) | 실계좌 | **매 주문 명시적 사용자 승인 필수** | ✗ | 미구현/비활성(설계만) |
| **AUTO_LIVE** | ✓ (Proposal) | 실계좌 | 사전 승인 전략·한도로 대체 | ✓ (한도 내) | 미구현/비활성(설계만) |

### 5.1 모드별 정의

- **RESEARCH:** 분석만 수행하며 주문을 생성하지 않는다. (기본 모드)
- **PAPER:** 내부 모의체결 또는 증권사 모의투자 계좌에서 거래한다.
- **GUARDED_LIVE:** 실계좌 주문 전마다 사용자의 명시적 승인을 받는다.
- **AUTO_LIVE:** 사전 승인된 전략과 한도 내에서만 자동 주문한다.

### 5.2 필수 기본 설정 (불변)

```
TRADING_MODE=RESEARCH
LIVE_TRADING_ENABLED=false
AUTO_EXECUTION_ENABLED=false
```

- 실거래 기능은 **명시적인 별도 요청 전까지** 구현하거나 활성화하지 않는다.
- **환경변수 하나만 변경하여 실거래가 활성화되는 구조를 만들지 않는다.** 실거래 경로는 `LIVE_TRADING_ENABLED`·`AUTO_EXECUTION_ENABLED`·모드·사람 승인/정책 승인이 모두 충족되어야 한다.
- 실거래 관련 설정 변경은 **별도 감사 로그 대상**이다.

### 5.3 모드 전이 시 안전 조건 (개념)

- RESEARCH → PAPER: 자격증명 분리(PAPER 전용) 확인. 실자금 영향 없음.
- PAPER → GUARDED_LIVE: `LIVE_TRADING_ENABLED=true` + 운영/모의 키 분리 + 모든 주문에 사람 승인 단계(`AWAITING_HUMAN`) + 대사 검증. (RUNBOOK의 "모의→실거래 전환 전 검증사항" 준수.)
- GUARDED_LIVE → AUTO_LIVE: `AUTO_EXECUTION_ENABLED=true` + 사전 승인된 StrategyVersion·RiskLimit + Kill Switch 가동 확인.

> 위 전이는 **최종 제품의 운영 절차**이며, 이번 빌드에서는 어떤 LIVE 전이도 수행/활성화하지 않는다.

---

## 6. 핵심 기능 (Core Features) + 우선순위

### 6.1 최종 16기능과 우선순위

우선순위 표기: **P0** = 안전·기반(Phase 0/1에서 골격 구현), **P1** = 핵심 분석(최종), **P2** = 트레이딩 실행(향후, 안전 게이트 뒤).

| # | 기능 | 우선순위 | 관련 메뉴(최종) | Phase 0/1 구현 수준 |
|---|---|---|---|---|
| 1 | 지수 분석(KOSPI/KOSPI200/KOSDAQ·시장지표) | P1 | 1·4 | 라우트/placeholder |
| 2 | 외국인·기관·개인 수급 분석 | P1 | 4 | 설계(도메인 모델) |
| 3 | 프로그램·선물옵션·공매도·변동성 분석 | P1 | 4 | 설계(도메인 모델) |
| 4 | 거시경제 지표 분석 | P1 | 3 | 에이전트 설계 |
| 5 | 환율·금리·원자재·글로벌 증시 분석 | P1 | 3 | 에이전트 설계 |
| 6 | 뉴스·국제정세 분석 | P1 | 3 | 에이전트 설계 |
| 7 | DART 공시·기업 이벤트 분석 | P1 | 6·7 | 에이전트 설계 |
| 8 | 섹터·종목 분석 | P1 | 5·6 | 라우트/placeholder |
| 9 | 주도 산업·테마 분석 | P1 | 7 | 설계 |
| 10 | 장기 성장 산업 탐색 | P1 | 7 | 설계(Structural Growth Scout) |
| 11 | **시장 국면 분류**(9국면) | P0/P1 | 2 | enum·설계 |
| 12 | 상승·하락 확률·정량 신호 | P1 | 2·4 | Signal 모델 설계 |
| 13 | 전략 백테스트 | P1 | 8 | 설계(point-in-time 원칙) |
| 14 | 모의매매(PAPER) | P2 | 8·9 | mock 인터페이스 |
| 15 | 사용자 승인형 실거래(GUARDED_LIVE) | P2 | 8·9 | 설계만, 비활성 |
| 16 | 제한적 자동매매(AUTO_LIVE) | P2 | 8·9 | 설계만, 비활성 |

> Phase 0/1의 실제 산출물은 **문서·기본 라우트·확장 가능한 구조·mock·도메인 모델·Risk Engine 골격·주문 상태 머신**이다. 10메뉴를 실제로 모두 구현하지 않는다.

### 6.2 시장 국면 9종 (Market Regime)

`/실시간 시장 국면` 메뉴와 Market Regime Engine이 분류하는 9개 국면.

| # | Regime | 의미(요약) |
|---|---|---|
| 1 | `RISK_ON_STRONG` | 강한 위험선호 |
| 2 | `RISK_ON_FRAGILE` | 위험선호이나 취약 |
| 3 | `LIQUIDITY_RALLY` | 유동성 주도 랠리 |
| 4 | `EARNINGS_RALLY` | 실적 주도 랠리 |
| 5 | `SIDEWAYS_LOW_VOL` | 저변동 횡보 |
| 6 | `SIDEWAYS_HIGH_VOL` | 고변동 횡보 |
| 7 | `RISK_OFF` | 위험회피 |
| 8 | `CRISIS` | 위기 |
| 9 | `DATA_UNCERTAIN` | 데이터 불확실 |

### 6.3 21개 분석 에이전트 (요약)

모든 에이전트는 **분석만** 하며 주문 권한이 없다. (상세는 `docs/AGENT_DESIGN.md`.)

1. Market Data Integrity Agent · 2. News Deduplication Agent · 3. Source Verification Agent · 4. Disclosure and Corporate Event Agent · 5. Korea Macro Agent · 6. Global Growth Agent · 7. Rates and Liquidity Agent · 8. FX Agent · 9. Commodity and Energy Agent · 10. Geopolitics and Trade Agent · 11. Foreign and Institutional Flow Agent · 12. Derivatives and Program Agent · 13. Breadth and Technical Agent · 14. Volatility and Regime Agent · 15. Earnings and Valuation Agent · 16. Technology and Semiconductor Agent · 17. Industrial and Export Agent · 18. Domestic Demand and Defensive Agent · 19. Structural Growth Scout · 20. Red-Team and Risk Agent · 21. Chief Market Synthesizer.

- 모든 에이전트 출력은 **버전이 있는 JSON Schema**를 사용하며 최소 필드: `agent_name, agent_version, as_of, horizon, direction, impact, confidence, thesis, evidence, counterevidence, affected_sectors, affected_symbols, invalidation_conditions, data_quality, model_name, prompt_version, created_at`.
- `evidence` 최소 필드: `source_id, source_type, title, url, published_at, available_at, claim`.
- **출처가 없는 주장은 최종 점수에 반영하지 않는다.**
- Phase 0/1에서는 실제 Anthropic API 호출 없이 **공통 인터페이스·Pydantic 모델·mock agent·검증 테스트**만 구현한다.

### 6.4 최종 정보구조 — 10메뉴

1. 오늘 · 2. 실시간 시장 국면 · 3. 거시·국제정세 · 4. 수급·기술적 분석 · 5. 섹터 · 6. 종목 · 7. 구조적 성장 산업 · 8. 트레이딩 랩 · 9. 계좌와 체결 · 10. 관리자.

> Phase 0/1에서는 이 메뉴를 모두 구현하지 않고 **문서·기본 라우트·확장 가능한 구조만** 설계한다.

---

## 7. 비기능 요구사항 (Non-Functional Requirements)

| 카테고리 | 요구사항 |
|---|---|
| **보안 (Security)** | `.env`는 Git 미포함, `.env.example`에는 변수명만(값 없음). 비밀값을 로그/API 응답/프런트엔드에 노출 금지. 입력값 검증, SQL injection 방지, CORS 기본값 제한. 서비스 간 권한 최소화. 운영/모의 키 분리, PAPER/LIVE 환경 분리. production secret을 Claude Code가 읽거나 출력하지 못함(문서화). |
| **안전 (Safety)** | LLM 에이전트는 주문 API 직접 호출 불가, 분석·Trade Proposal만 생성. 모든 주문은 deterministic Risk Engine(deny-by-default) 선행 승인. Execution Gateway는 Agent Service와 격리(네트워크 수준 분리 가능). Agent Service는 `BrokerAdapter.submit_order()` 접근 불가. 실거래 기본 비활성. 단일 환경변수로 실거래 활성화 불가. 리스크 통제를 테스트 통과 목적으로 약화 금지. |
| **무결성 (Integrity)** | 모든 주문에 idempotency key. 동일 idempotency key 중복 주문 거부. 주문 제출 후 브로커 체결 내역과 내부 장부 대사 필수. 잘못된 주문 상태 전이는 예외 발생. |
| **정확성 / Point-in-time** | 모든 datetime은 timezone-aware. 내부 저장 UTC, 화면 표시 Asia/Seoul. 4시점(`event_time/published_at/available_at/ingested_at`) 보존. `available_at` 이후에만 전략 사용. 미래 데이터의 과거 백테스트 유입 차단. money/price는 `Decimal`(float 금지). |
| **관측성 (Observability)** | 구조화 JSON 로그. 공통 health check. (확장 가능 구조로) OpenTelemetry / Prometheus·Grafana / Sentry. `/system`·`GET /api/v1/system/status`로 서비스·데이터 소스 상태 가시화. |
| **감사 (Audit)** | Audit Log는 일반 애플리케이션 흐름에서 임의 삭제 불가하도록 설계(불변성 원칙, ADR-006). 중요 상태 변경 기록. 실거래 설정 변경은 별도 감사 대상. `GET /api/v1/audit-logs`는 pagination·민감정보 제외. |
| **가용성 (Availability)** | Redis 미설정/미가동 시 **fakeredis 폴백** + 상태 정직 보고. DB는 `DATABASE_URL` 한 줄로 SQLite↔Postgres 전환. 서비스별 health check 및 의존성 설정(compose). |
| **성능 (Performance)** | 조회 API는 합리적 응답성을 목표로 한다. 본 Phase에서는 정량적 SLA를 강제하지 않으며, 향후 시계열/캐시(Redis) 도입 시 구체화한다. |
| **이식성 (Portability)** | 무도커 로컬모드(SQLite + fakeredis)와 Docker/Postgres/Redis 환경 양립. Alembic 단일 마이그레이션이 SQLite·Postgres 모두에서 동작(JSONB/네이티브 UUID 회피). |

> 표기된 OpenTelemetry/Prometheus/Grafana/Sentry/TimescaleDB/pgvector 등은 **확장 가능 구조**로 설계하며, Phase 0/1에서 실제 구동을 강제하지 않는다.

---

## 8. MVP 범위 (Phase 0 / Phase 1)

이번 빌드는 **Phase 0 + Phase 1만** 완성한다. Phase 2 이상은 구현하지 않는다.

### 8.1 Phase 0 — 설계 및 정책 문서

| 산출물 | 내용 |
|---|---|
| `docs/ULTRAPLAN.md` | 전체 요구사항 설계 문서화 |
| `docs/PRODUCT_SPEC.md` | **(본 문서)** 제품 목표·사용자·시나리오·운용 모드·핵심 기능·비기능·MVP·제외·성공기준 |
| `docs/ARCHITECTURE.md` | 시스템 구성도, 서비스 책임, 데이터 흐름, LLM/주문 경계, Agent↔Execution 분리 |
| `docs/TRADING_SAFETY.md` | 실거래 기본 비활성, Risk Engine 선행 승인, 상태 머신, idempotency, 대사, Kill Switch, PAPER/LIVE 분리, Auto Live 조건 |
| `docs/THREAT_MODEL.md` | 위협별 공격 경로/영향/탐지/예방/대응 |
| `docs/DATA_DICTIONARY.md` | 핵심 도메인 모델·필드·타입·시점 의미 |
| `docs/AGENT_DESIGN.md` | 21에이전트 역할·공통 I/O·Structured Output·Red-Team·Chief·주문권한 없음 원칙 |
| `docs/RUNBOOK.md` | 로컬 실행·환경변수·migration·상태 확인·로그·장애 대응·백업·Kill Switch·모의→실거래 전환 검증 |
| `docs/adr/ADR-001 ~ ADR-012` | 핵심 설계 결정(ADR-011 src-layout, ADR-012 npm workspaces+venv·asyncpg prod-only·fakeredis 포함) |
| `CLAUDE.md` | 프로젝트 안전·아키텍처·품질·트레이딩 규칙 |
| `.env.example` | 변수명만(값 없음) |

**Phase 0 완료 기준:** 필수 설계 문서·필수 ADR·`CLAUDE.md` 존재, 실거래 안전 원칙 명시, LLM/주문 실행 경계 명시, point-in-time 데이터 원칙 명시, Risk Engine deny-by-default 원칙 명시.

### 8.2 Phase 1 — 프로젝트 기반 구현

- **서비스 5종:** `apps/web`(Next.js), `apps/api`(FastAPI), `apps/worker`(APScheduler), `apps/agent-service`, `apps/execution-gateway`. Agent↔Execution 보안 격리.
- **인프라:** 환경설정 모듈, 구조화 로깅, DB(SQLAlchemy+Alembic, 기본 SQLite), Redis(fakeredis 폴백), 공통 health check.
- **도메인:** time/money/enums, `AgentFinding`·`Evidence`(`source_id` 필수), `AgentRun`. money/price는 Decimal.
- **DB 우선 6테이블:** `instruments, agent_runs, agent_findings, risk_decisions, order_proposals, audit_logs` + Alembic(가능한 한 reversible).
- **Risk Engine:** deny-by-default 기본 구조 + `RiskDecision` 모델 + `risk_limits.yml` 초안 + 최소 규칙.
- **브로커/실행:** `BrokerAdapter` Protocol + `MockBrokerAdapter`(안전 stub, 실주문 없음) + 주문 상태 머신(13상태, 불법 전이 raise). Agent Service가 `submit_order`를 import/호출하지 못함을 테스트로 강제.
- **에이전트:** mock 21에이전트 레지스트리(실제 Anthropic 호출 없음).

#### Phase 1 — 웹 5페이지

| 라우트 | 내용 |
|---|---|
| `/` | 소개, 현재 운용 모드, `LIVE TRADING DISABLED` 표시, 시스템 상태, 향후 메뉴 구조 |
| `/dashboard` | placeholder 대시보드, 실데이터 없음 명시(`MOCK DATA` 배너) |
| `/agents` | mock agent 목록, agent schema 예시, mock 실행 결과 |
| `/risk` | Risk Engine 설명, deny-by-default 상태, 테스트 Proposal 입력·평가 UI(**실주문 버튼 없음**) |
| `/system` | API/DB/Redis 상태, 앱 버전, 환경, trading mode, live trading disabled |

#### Phase 1 — API 7엔드포인트

| Method · Path | 내용 |
|---|---|
| `GET /health` | API/DB/Redis 상태, trading mode, live trading enabled 여부(**비밀값 미반환**) |
| `GET /api/v1/system/status` | 서비스 버전·환경·서버 시각·trading mode·기능 플래그·데이터 소스 상태 placeholder |
| `GET /api/v1/agents` | 등록된 mock agent 목록(이름/버전/활성화 여부) |
| `POST /api/v1/agents/mock-run` | mock agent 실행, AgentFinding Schema 검증(**실 Anthropic 호출 없음**) |
| `POST /api/v1/order-proposals/validate` | OrderProposal Schema 검증(**실주문 없음**) |
| `POST /api/v1/risk/evaluate` | deny-by-default Risk Engine 실행, 테스트 Proposal 승인/거절(**실주문 없음**) |
| `GET /api/v1/audit-logs` | 개발용 Audit Log 조회(pagination, 민감정보 제외) |

- **품질 게이트(로컬 실제 실행):** `ruff check` · `mypy` · `pytest` · (web) `eslint` · `tsc --noEmit` · `next build` · `alembic upgrade head`(sqlite)→`downgrade base`.
- **테스트:** 스펙 §22의 15개 테스트(특히 #8 Agent Service가 `submit_order`에 접근 불가).
- **CI:** Backend(ruff/mypy/pytest) + Frontend(npm install/lint/typecheck/test/build) + `.env`/credential commit 검사 + migration 검사.

**Phase 1 완료 기준:** API·Web·DB·Redis 연결, 모든 서비스 health check, 핵심 도메인 모델, AgentFinding Schema, BrokerAdapter·MockBrokerAdapter, deterministic Risk Engine 기본 구조, 주문 상태 머신, 최소 API/UI, Alembic migration, 테스트/lint/typecheck/frontend build 통과, **실거래 기능 없음**, mock이 실데이터로 오인되지 않음, 비밀값이 코드/로그에 없음. (Docker Compose 실행은 본 장비 Docker 미설치로 **미검증 명시**.)

---

## 9. 명시적 제외 범위 (Out of Scope)

이번 빌드(Phase 0/1)에서 **명시적으로 제외**한다.

| 제외 항목 | 사유 / 비고 |
|---|---|
| **실거래(Live Trading)** | `LIVE_TRADING_ENABLED=false` 유지. 실주문 경로 미구현·비활성. |
| **실 브로커 연동** | 한국투자증권(KIS)·키움증권 실 API 연결 미구현. `BrokerAdapter` Protocol + `MockBrokerAdapter`만. |
| **실 Anthropic API 호출** | 에이전트는 mock만. 실제 LLM 호출 없음. Structured Output 스키마·검증만. |
| **실 시장 데이터** | DART/ECOS/FRED/NAVER 등 실데이터 수집 없음. 전부 mock + `MOCK DATA — NOT REAL MARKET DATA` 배너. |
| **자동매매(AUTO_LIVE) 동작** | `AUTO_EXECUTION_ENABLED=false`. 설계만, 미동작. |
| **10메뉴 전체 UI** | Phase 1은 웹 5페이지만. 나머지는 라우트/구조 설계만. |
| **Docker Compose 실제 구동** | 파일은 작성하되 본 장비 Docker 미설치 → `docker compose up` 미실행/미검증(보고서에 정직히 명시). |
| **Cloudflare 운영 배포** | Named Tunnel/Access 등 운영 배포는 향후(ADR-007 설계만). |
| **Phase 2 이상 전 기능** | 본 빌드 종료 후 중단. |

> **위장 금지:** mock을 실데이터로 표시하지 않으며, 통과하지 못한 검증을 통과한 것처럼 보고하지 않는다.

---

## 10. 성공 기준 / KPI (Success Criteria)

### 10.1 안전 KPI (필수 · 0 허용)

| KPI | 목표 | 검증 |
|---|---|---|
| LLM/Agent의 실주문 발생 | **0건** | 구조적 격리 + 테스트 #8(`submit_order` import/호출 불가) |
| 테스트에서 실제 주문 전송 | **0건** | 전 테스트 mock, 실주문 경로 없음 |
| 단일 환경변수로 실거래 활성화 | **불가능** | 다중 플래그·승인 게이트 |
| 비밀값의 코드/로그/API/프런트 노출 | **0건** | 테스트 #11(비밀값 비노출), `.env.example` 변수명만 |
| `RiskDecision` 없이 `ApprovedOrder` 생성 | **불가능** | 팩토리 raise(테스트 #4) |
| 미등록 종목/미승인 전략 주문 | **전부 거절** | deny-by-default(테스트 #5) |
| 중복 idempotency key 주문 | **거부** | 테스트 #10 |
| 잘못된 주문 상태 전이 | **예외 발생** | 테스트 #9 |

### 10.2 정확성 / 데이터 KPI

| KPI | 목표 |
|---|---|
| money/price에 float 사용 | **0건**(Decimal만, 테스트 #1) |
| timezone-naive datetime | **거부**(테스트 #2) |
| Evidence의 `source_id` 누락 허용 | **불가**(테스트 #3) |
| `LIVE_TRADING_ENABLED` 기본값 | **false**(테스트 #6) |
| `AUTO_EXECUTION_ENABLED` 기본값 | **false**(테스트 #7) |

### 10.3 기능·완성도 KPI (Phase 1)

| KPI | 목표 |
|---|---|
| API 7엔드포인트 동작 | 7/7 |
| 웹 5페이지 렌더 | 5/5 |
| 서비스 health check | 전 서비스 정상 보고(fakeredis 폴백 시 정직 보고) |
| 품질 게이트 통과 | `ruff`/`mypy`/`pytest`/`eslint`/`tsc --noEmit`/`next build`/`alembic upgrade→downgrade` 전부 통과 |
| 스펙 §22 테스트 | 15/15 통과 |
| Audit Log 기록 | 중요 상태 변경 기록(테스트 #15) |
| mock 데이터 오인 | **0건**(배너 표기) |

### 10.4 제품 가치 KPI (향후 측정 — 정성/방향성)

- P-INV: 오늘 화면에서 "현재 시장 국면 + 주도 섹터/종목 + 근거"를 단일 화면에서 파악 가능.
- P-RES: 모든 분석 결론이 `source_id`로 추적 가능, 백테스트가 point-in-time으로 재현 가능.
- P-RISK: 모든 주문 후보가 Risk Engine을 거치고, 모든 중요 상태 변경이 감사 가능.

---

## 11. 가정과 제약 (Assumptions & Constraints)

### 11.1 환경 가정

- Windows 11 / PowerShell / Node v24.15.0 / npm 11.12.1 / Python 3.14.4 / git 2.54.
- **Docker · PostgreSQL · Redis · pnpm 은 본 장비에 미설치.**
- 프로젝트 루트 = `C:\Users\andul\kospi-watcher` (그 자리에서 초기화, 이중 중첩 금지).

### 11.2 아키텍처 제약 (무도커 로컬모드)

- DB는 `DATABASE_URL` 한 줄 전환: 로컬/CI 기본 = SQLite(aiosqlite), 프로드/Docker = Postgres(asyncpg). **asyncpg는 prod-only/optional**(로컬 설치 강제 금지).
- Redis 미설정/미가동 시 **fakeredis 폴백** + 상태 정직 보고. docker-compose에는 실제 redis.
- Alembic 단일 마이그레이션은 SQLite·Postgres 양립(JSONB/네이티브 UUID 회피, `Numeric`·`DateTime(timezone=True)`·`JSON`·`String` 사용).
- worker = **APScheduler**(Celery/Redis 브로커 아님).
- 프런트 = **npm workspaces**(pnpm 없음). 백엔드 = 단일 venv + src-layout 패키지 `kospi_watcher`(`src/kospi_watcher/{domain,adapters,infrastructure}`).

### 11.3 금융 / 안전 규약 (불변)

- money/price는 **Decimal**(SQLAlchemy `Numeric`, Pydantic `Decimal`). float 금지.
- 브로커 인터페이스 메서드명 = `submit_order(order: ApprovedOrder)`. 구현은 `domain/execution/broker` + `apps/execution-gateway`에만 둔다.
- `apps/agent-service`와 `domain/agents` 소스에는 `submit_order` import 경로가 없도록 구조화(소스 문자열/AST 스캔 + import 단언 테스트 = 스펙 테스트 #8).
- `ApprovedOrder`는 `APPROVED` 상태의 `RiskDecision` 없이는 생성 불가(팩토리 raise). 중복 idempotency_key 거부.
- 실거래·실 브로커·실 Anthropic 호출·실 시장데이터 없음. **mock만.**

### 11.4 프로세스 제약

- `git init`은 하되 commit은 사용자가 요청하기 전까지 하지 않는다.
- 형제 프로젝트(`C:\Users\andul\krw-watcher`, `C:\Users\andul\fed-watcher`)는 절대 수정하지 않는다.
- 사소한 선택은 합리적 기본값 + ADR/보고서 기록. 큰 빌드 중 확인 질문 자제, 끝까지 완주.
- 완료 후 스펙 §27 형식으로 보고하고, 실패/미검증 항목을 숨기지 않는다.

### 11.5 알려진 리스크

| 리스크 | 영향 | 완화 |
|---|---|---|
| Python 3.14 휠 호환성 | 패키지 설치 실패 | Step 0에서 venv·로컬 세트(asyncpg 제외) 선설치로 사전 제거 |
| SQLite↔Postgres 마이그레이션 비호환 | migration 실패 | JSONB/네이티브 UUID 회피, 호환 타입만 사용 |
| Docker 미설치 | compose 미검증 | 작성만, `docker compose up` 미실행 → 보고서에 "미검증(Docker 미설치)" 명시 |
| mock의 실데이터 오인 | 잘못된 신뢰 | `MOCK DATA — NOT REAL MARKET DATA` 배너 + 상태 정직 보고 |

---

## 12. 예측 엔진 & 데일리 브리핑 (Prediction Engine & Daily Brief)

> 본 장은 형제 시스템(Fed-Watcher, KRW-Watcher)과 같이 제품의 **무게중심을 "예측 + 데일리 브리핑"**으로 이동시킨다. 트레이딩(모의/페이퍼)은 **부차적**이며 안전 게이트 뒤에 머문다(§5, §6.1의 P2 기능). 상세 동작은 `docs/ARCHITECTURE.md` §4d·§4e, `docs/AGENT_DESIGN.md` §7, ADR-016·ADR-017 참조.

### 12.1 제품 강조점 — 예측 + 브리핑이 1차 산출물

KOSPI-WATCHER의 **1차 산출물**은 매 실행마다 생성되는 **하우스 시장 예측(house market prediction)**과 그에 딸린 **단일 서사형 한국어 데일리 브리핑**이다. 21개 분석 에이전트의 finding을 종합해 (a) 오늘의 **시장 국면(regime)**, (b) **방향성(direction)·확신도(confidence)**, (c) **롱/인버스/곱버스 포지셔닝**, (d) **3개 시나리오**, (e) 이를 하나의 이야기로 엮은 **브리핑**을 제시한다.

핵심 원칙은 §1.3을 그대로 따른다: **예측 종합기(synthesizer)는 deterministic 코드**다. 에이전트 finding이 mock 런타임에서 왔든 실제 LLM 런타임에서 왔든, 동일한 finding 집합이면 동일한 예측이 나온다(`generated_by`에 입력 출처만 `"mock"|"llm"`으로 정직히 기록). 즉 "분석(가변)은 에이전트, 종합·확률·포지셔닝(불변)은 결정론 코드"라는 경계가 예측 단계에도 그대로 적용된다.

### 12.2 계층형 리서치 데스크 조직 (5 데스크 + Chief, 3 티어)

21개 에이전트는 평평한 목록이 아니라 **리서치 회사**처럼 조직된다(`domain/agents/org.py`, ADR-016). 5개 **데스크**(각 *리드* 지정)가 1명의 **Chief**에게 보고하며, 작업은 **티어** 순으로 흐른다: `VALIDATE → ANALYZE → SYNTHESIZE`. 각 분석 데스크는 Chief 종합 시 사용하는 **방향성 가중치(weight)**를 가진다.

| 데스크 | 티어 | 가중치 | 리드 | 멤버 수 |
|---|---|---|---|---|
| `DATA_INTEGRITY` (데이터·검증) | `VALIDATE` | 0.10 | Market Data Integrity Agent | 3 |
| `MACRO` (거시·국제) | `ANALYZE` | 0.24 | Korea Macro Agent | 6 |
| `FLOW_TECH` (수급·기술) | `ANALYZE` | 0.26 | Foreign and Institutional Flow Agent | 4 |
| `FUNDAMENTAL` (실적·섹터) | `ANALYZE` | 0.24 | Earnings and Valuation Agent | 5 |
| `RISK` (리스크·레드팀) | `ANALYZE` | 0.16 | Red-Team and Risk Agent | 2 |
| `CHIEF` (수석 신디사이저) | `SYNTHESIZE` | 0.00 | Chief Market Synthesizer | 1 |

데스크 뷰는 **임팩트×확신, 리드 가중(×1.5)**으로 산출되고, Chief는 이를 **데스크 가중치로 가중합**하여 하우스 방향성·확신도를 만든다(`domain/prediction/synthesizer.py`). `GET /api/v1/agents/org`가 이 조직도를 읽기 전용으로 노출한다.

### 12.3 시장 국면 9종 (재확인)

예측은 §6.2의 **9개 `MarketRegime`** 중 하나로 오늘을 분류한다(`domain/prediction/regime.py`의 `classify_regime`). 예: 약세 + 고위험 + 고확신 → `CRISIS`; 강세 + 고확신 + 저변동 → `RISK_ON_STRONG`; 데이터 불량 → `DATA_UNCERTAIN`. 9종 목록은 §6.2 표와 동일하다.

### 12.4 롱/숏 상품 사다리 (인버스/곱버스)

예측은 **방향성을 실행 가능한 포지셔닝**으로 번역하기 위해 **롱/숏 레버리지 사다리**를 사용한다(`domain/prediction/instruments.py`). 약세 뷰는 단순 "롱 회피"가 아니라 **인버스/곱버스 비중확대(overweight)**로 표현된다.

| 종목코드 | 이름 | `InstrumentKind` | 익스포저 |
|---|---|---|---|
| `069500` | KODEX 200 | `LONG_1X` | +1× 롱 |
| `122630` | KODEX 레버리지 | `LONG_2X` | +2× 롱 |
| `114800` | KODEX 인버스 | `INVERSE_1X` | −1× 숏 |
| `252670` | KODEX 200선물인버스2X (**곱버스**) | `INVERSE_2X` | −2× 숏 |

`stance_for(kind, direction, confidence, regime)`가 종목별 `StanceLabel`(`OVERWEIGHT`/`NEUTRAL`/`UNDERWEIGHT`/`AVOID`)을 산출한다. 뷰와 **정합**하는 상품은 확신도가 높을수록 `OVERWEIGHT`로, **역행**하는 상품은 `UNDERWEIGHT`/`AVOID`로 기운다. 모든 **2배 레버리지 상품**(`LONG_2X`, 곱버스 `INVERSE_2X`)은 *"레버리지·일일 리밸런싱에 따른 변동성 손실(데케이) 위험 — 장기 보유 부적합"* 리스크 노트를 달고, 고변동·`CRISIS` 국면에서는 방향이 맞아도 `NEUTRAL`/`AVOID`로 끌린다.

> 주의: 이 종목들은 예측·포지셔닝 **표시용**이다. `config/instruments.yml`에서 `122630`/`114800`/`252670`은 `tradable=false`이고, 매매 경로는 deny-by-default Risk Engine의 `allowed_instruments` 화이트리스트(§6.1 P2, ADR-010)를 별도로 통과해야 한다. 예측이 곧 주문 권한을 의미하지 않는다.

### 12.5 산출물·영속화·엔드포인트·워커

- **산출물:** `MarketPrediction`(`domain/prediction/schemas.py`, `PREDICTION_SCHEMA_VERSION="1.0.0"`) — `regime`, `direction`, `confidence`, `data_quality`, `headline`, 단일 서사 `brief`, `desk_views`, `instrument_stances`, 3개 `scenarios`(확률 합 1.0), `generated_by`(`"mock"|"llm"`), `agent_count`.
- **브리핑:** 분절 캡션이 아니라 **하나의 한국어 서사**(국면 → 하우스 방향·확신 → 주도 데스크 근거 → 리스크 데스크 경고·무효화 조건 → 롱/인버스/곱버스 포지셔닝)로 작성된다.
- **영속화:** 새 테이블 `market_predictions`(`PredictionRow`, Alembic `0003_predictions.py`)에 저장된다(스칼라 컬럼 + 전체 `payload` JSON).
- **엔드포인트(`/api/v1`):** `POST /prediction/run`(전 에이전트 실행→종합→저장→반환), `GET /prediction/latest`, `GET /brief`, `GET /agents/org`.
- **워커:** `refresh_prediction` 잡이 **30분마다** 예측을 재생성·영속화하여 `/prediction/latest`·`/brief`를 최신으로 유지한다(`worker/scheduler.py`). 이때 최근 스크랩 뉴스 헤드라인을 함께 반영한다(§13.1).

### 12.6 예측 라벨링 — 무엇을, 어느 기간에 대해 (subject + horizon)

예측은 이제 **무엇에 대한 예측인지(subject)**와 **어느 기간에 대한 예측인지(horizon)**를 명시적으로 라벨한다. `MarketPrediction`은 `subject`(기본 `"코스피200 지수 방향"`; 종합기는 `"코스피200 지수 방향 (KODEX 200 추종 기준)"`로 채움)와 `horizon`(기본 `D5`)에 더해 사람이 읽을 수 있는 `horizon_label`(예: `"단기 (약 1주, D5)"`)을 담는다. 웹 `오늘`·`예측` 화면은 이 **예측 대상 / 기간** 라벨을 상단에 함께 표기하므로, 사용자는 숫자만 보는 것이 아니라 "코스피200 방향을 약 1주 시계로 본 예측"임을 분명히 알 수 있다.

---

## 13. 뉴스 스크랩 & 에이전트 논의 가시화 (News Scraping & Visible Deliberation)

> 본 장은 데일리 브리핑을 **뉴스 근거**로 보강하고, 예측을 만든 **에이전트 논의 과정**을 사용자에게 보여주는 두 신규 기능을 요약한다. 상세 동작은 `docs/ARCHITECTURE.md` §4f·§4g·§6a, `docs/AGENT_DESIGN.md` §7.5·§7.6, ADR-018·ADR-019 참조.

### 13.1 뉴스 스크랩 & 데일리 브리프 근거

데일리 브리핑이 **일자별로 스크랩된 한국 증시 뉴스**를 근거로 함께 제시한다.

- **키리스 수집:** Google News RSS(검색 엔드포인트)에서 **API 키 없이** 설정된 토픽(`news_topics`, 기본 `코스피 증시`·`코스닥`·`원달러 환율`·`삼성전자 반도체`)을 수집한다. XML은 **`defusedxml`**로 안전하게 파싱하며, 제공자는 어떤 오류에도 예외를 던지지 않고 빈 목록을 반환해 안전하게 열화한다(`news_provider`로 `google`/`mock` 선택). 오프라인 `mock` 제공자는 `[MOCK]` 라벨 헤드라인만 낸다(원칙 §1.3 "Mock은 mock으로").
- **일자별 저장 + 보존(retention):** 항목은 `news_items` 테이블(Alembic `0004_news.py`)에 저장되며, KST 캘린더 일자(`date_kst`)로 묶인다. 매 스크랩마다 **토픽 간 중복을 id로 제거**해 upsert하고, **`news_retention_days`(기본 14일)**보다 오래된 항목은 **자동 삭제(prune)**하여 피드가 무한정 쌓이지 않는다.
- **브리프 근거로 사용:** 예측 생성 시(라우트·워커) `recent_headlines`(최신 스크랩 제목)를 종합기에 전달하면, 브리프 서사에 최근 흐름이 반영되고 최대 5건이 `news_refs`로 함께 표시된다. 단, 뉴스는 **서사·참고용**일 뿐 결정론적 데스크/수석 종합 수치를 바꾸지 않으며, 에이전트는 여전히 분석만 한다(주문 권한 없음).
- **엔드포인트(`/api/v1`)·워커:** `GET /news`(일자 필터 가능), `GET /news/dates`(일자별 건수), `POST /news/scrape`(즉시 수집). 워커 `scrape_news` 잡이 **60분마다** 동일 경로를 수행한다. 웹 `뉴스` 페이지가 일자별로 묶어 보여준다.

### 13.2 에이전트 논의 가시화 (Visible Deliberation)

예측이 **그 예측을 만든 논의 과정**을 함께 담아 사용자에게 보여준다 — 더 이상 블랙박스가 아니다. 종합기는 §12.2의 수치 종합과 **동일한 결정론적 패스**에서 논의 기록(`Deliberation`)을 만든다(추가 LLM 호출·추가 실행 없음, 재현 가능).

- **데스크 내부(데스크 토의 → 리드 조율):** 각 응답 에이전트의 입장(`AgentPosition` — 방향·확신·요지, 리드 표시)을 기록하고, 데스크 합의(`consensus` = 데스크 lean)와 **합의도(agreement = 합의 인원 / 응답 인원)**, **이견(dissent, 반대 방향 멤버)**을 산출하며, 리드가 "N/M건 합의, 이견 K건은 리드가 가중·조율" 식으로 정리한다(`lead_note`).
- **데스크 간(수석 조율):** 수석은 4개 방향성 데스크를 하우스 방향과 비교해 **지지 데스크(aligned)**와 **이견 데스크(conflicted)**로 나누고, 지지 가중치 합과 함께 "몇 개 데스크가 어느 가중으로 지지, 몇 개는 이견 → 하우스 방향 확정(확신 X%)"을 기록한다(`ChiefDeliberation.note`).
- **노출:** 웹 `예측` 페이지가 이 과정을 **스레드**로 렌더한다 — 데스크별 카드(에이전트 입장·이견 강조) → 수석 종합 카드(지지/이견 데스크). 즉 "왜 이 방향인가"가 데스크 토의→수석 조율의 한 흐름으로 드러난다.

### 13.3 UI·면책·소유권 (참고)

웹은 **다중 페이지 모던 UI**(Pretendard 폰트, 다크 핀테크 팔레트)로 재설계되었고 `오늘 / 예측 / 뉴스 / 에이전트 / 트레이딩 / 시스템` 내비게이션을 가진다. 한국 관습대로 **상승=빨강, 하락=파랑**이다. 모든 페이지 하단에 **면책 고지**(정보 제공 목적·투자 자문 아님, 예측·스탠스는 알고리즘/에이전트 참고 자료, 인버스·레버리지(곱버스)의 데케이·원금 손실 위험, 실거래 미제공)와 **소유권**(`© 2026 YellowScale · 안민규(Minkyu An)`)이 표기된다. 상세는 ARCHITECTURE §6a.

---

> **요약:** KOSPI-WATCHER는 "분석은 LLM, 실행은 deterministic 코드"라는 경계 위에 세워진, 안전 우선의 한국 증시 분석·트레이딩 리서치 시스템이다. 제품의 무게중심은 이제 **예측 + 데일리 브리핑**(계층형 5데스크+Chief 조직이 종합, 롱/인버스/곱버스 포지셔닝 포함)이며, 트레이딩은 부차적·페이퍼 한정이다. 모든 안전 불변식은 테스트로 강제되고, 예측 종합기는 mock·LLM finding 위에서 결정론적으로 동작한다.
