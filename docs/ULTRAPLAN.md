# KOSPI-WATCHER — ULTRAPLAN (마스터 설계 문서)

> 본 문서는 KOSPI-WATCHER 프로젝트의 **단일 권위 설계 문서(master design document)**다.
> 모든 하위 문서(`PRODUCT_SPEC`, `ARCHITECTURE`, `TRADING_SAFETY`, `THREAT_MODEL`,
> `DATA_DICTIONARY`, `AGENT_DESIGN`, `RUNBOOK`)와 ADR, 구현 코드는 이 문서와 100% 일치해야 한다.
> 출처: `_KICKOFF.md` = (A) 확정 결정 오버레이 + (B) 원본 스펙 전문. 스펙과 오버레이가 충돌하면 **오버레이가 우선**한다.
>
> **이번 빌드 범위: Phase 0(설계 문서) + Phase 1(기반 구현)만.** 전부 mock이며 실거래는 없다.
> Phase 2 이상은 구현하지 않는다.

---

## 1. 개요와 최종 목표

KOSPI-WATCHER는 한국 증시(KOSPI / KOSPI200 / KOSDAQ)의 가격·수급·거시경제·국내외 정세·뉴스·공시·섹터·종목·구조적 성장 산업을 하나의 웹사이트에서 분석하고, 향후 증권사 계좌와 연결하여 KOSPI 또는 KOSPI200 연계 ETF의 모의매매와 **리스크 통제형 자동매매**를 수행하는 시스템이다.

핵심 철학은 **분석과 실행의 엄격한 분리**다. LLM 에이전트는 분석과 Trade Proposal만 생성하고, 모든 주문은 LLM을 사용하지 않는 deterministic Risk Engine의 승인을 거친다. 실거래는 기본 비활성화이며, 명시적인 별도 요청 전까지 구현·활성화하지 않는다.

### 1.1 16개 최종 기능

| # | 기능 |
|---|------|
| 1 | KOSPI, KOSPI200, KOSDAQ 및 주요 시장지표 분석 |
| 2 | 외국인·기관·개인 수급(Investor Flow) 분석 |
| 3 | 프로그램 매매, 선물·옵션(Derivatives), 공매도 및 변동성 분석 |
| 4 | 국내외 거시경제 지표 분석 |
| 5 | 환율(FX), 금리(Rates), 원자재(Commodity), 글로벌 증시 분석 |
| 6 | 국내외 주요 뉴스와 국제정세(Geopolitics) 분석 |
| 7 | DART 공시 및 기업 이벤트 분석 |
| 8 | 주요 섹터(Sector)와 종목(Symbol) 분석 |
| 9 | 현재 시장을 주도하는 산업과 테마 분석 |
| 10 | 장기적으로 성장 가능성이 큰 산업 탐색(Structural Growth) |
| 11 | 시장 국면(Market Regime) 분류 |
| 12 | 지수 상승·하락 확률 및 정량 신호(Signal) 산출 |
| 13 | 전략 백테스트(Backtest) |
| 14 | 모의매매(Paper Trading) |
| 15 | 사용자 승인형 실거래(Guarded Live) |
| 16 | 엄격한 리스크 통제 하의 제한적 자동매매(Auto Live) |

### 1.2 4개 운용 모드

| 모드 | 설명 | 주문 생성 |
|------|------|-----------|
| `RESEARCH` | 분석만 수행. 주문을 생성하지 않는다. **(기본값)** | 없음 |
| `PAPER` | 내부 모의체결 또는 증권사 모의투자 계좌에서 거래 | 모의 |
| `GUARDED_LIVE` | 실계좌 주문 전마다 사용자의 명시적 승인을 받음 | 승인 후 실주문 |
| `AUTO_LIVE` | 사전 승인된 전략과 한도 내에서만 자동 주문 | 정책 승인 후 자동 |

### 1.3 강제 기본값 (불변)

```
TRADING_MODE=RESEARCH
LIVE_TRADING_ENABLED=false
AUTO_EXECUTION_ENABLED=false
```

실거래 기능은 명시적인 별도 요청 전까지 구현하거나 활성화하지 않는다. 환경변수 하나만 변경해서 실거래가 켜지는 구조는 금지한다(§2-19).

---

## 2. 절대적인 아키텍처 원칙 20개 (스펙 §2 전부)

다음 원칙은 **절대로 위반하면 안 된다.** 테스트를 통과시키기 위해서도, 편의를 위해서도 약화할 수 없다.

| # | 원칙 | 강제 방법 (Phase 1) |
|---|------|---------------------|
| 1 | LLM 에이전트는 증권사 주문 API를 직접 호출할 수 없다. | 패키지 경계 + import 스캔 테스트(테스트 #8) |
| 2 | LLM 에이전트는 시장 분석 결과와 Trade Proposal만 생성한다. | `agent_service`는 `OrderProposal`까지만 생성, `ApprovedOrder` 불가 |
| 3 | 모든 주문은 deterministic Risk Engine의 승인을 받아야 한다. | `ApprovedOrder` 팩토리는 APPROVED `RiskDecision` 요구 |
| 4 | Risk Engine은 LLM 없이 순수 코드와 명시적 규칙으로 구현한다. | `domain/risk`는 LLM/네트워크 의존성 없음, deny-by-default |
| 5 | Execution Gateway는 Agent Service와 별도 서비스로 격리한다. | `apps/execution-gateway` ↔ `apps/agent-service` 분리 |
| 6 | Agent Service는 `BrokerAdapter.submit_order()`에 접근할 수 없다. | `submit_order` 임포트 경로 부재 + AST/문자열 스캔 테스트 |
| 7 | 실거래는 기본적으로 비활성화한다. | `LIVE_TRADING_ENABLED=false` 기본(테스트 #6) |
| 8 | 실거래 API 키·계좌번호·비밀번호·토큰을 코드·로그·프런트엔드에 노출하지 않는다. | `.env.example`은 변수명만, secret 마스킹, API 응답 제외(테스트 #11) |
| 9 | 모든 주문에는 idempotency key가 있어야 한다. | `OrderProposal`/`ApprovedOrder`에 `idempotency_key` 필수 |
| 10 | 주문 제출 후 브로커 체결 내역과 내부 장부를 반드시 대사한다. | 상태 머신에 `RECONCILIATION_ERROR`, 대사 로직 설계 |
| 11 | Broker별 API 명세가 전략 코드에 직접 침투하지 않게 한다. | `BrokerAdapter` Protocol로 격리 |
| 12 | 전략 코드와 브로커 구현은 인터페이스로 분리한다. | `domain/strategies` ↔ `domain/execution/broker` 분리 |
| 13 | 모든 외부 데이터는 typed adapter를 통해 수집한다. | `adapters/*` (dart/ecos/fred/news/brokers) typed |
| 14 | 모든 에이전트 출력은 버전이 있는 JSON Schema를 사용한다. | `AgentFinding` + `prompt_version`/`agent_version`, JSON Schema export |
| 15 | 모든 금융 데이터에는 시점 정보를 보존한다. | `event_time`/`published_at`/`available_at`/`ingested_at` |
| 16 | 가짜 금융 데이터를 실제 데이터처럼 표시하지 않는다. | "MOCK DATA — NOT REAL MARKET DATA" 배너 |
| 17 | 공식 API 명세가 불확실하면 추측하여 구현하지 않는다. | KIS/Kiwoom 실연동 미구현, mock stub만 |
| 18 | 테스트를 통과시키기 위해 리스크 통제를 약화하지 않는다. | deny-by-default 유지, 테스트가 통제를 우회하지 않음 |
| 19 | 환경변수 하나만 변경하여 실거래가 활성화되는 구조를 만들지 않는다. | 다중 플래그(`TRADING_MODE`+`LIVE_TRADING_ENABLED`+`AUTO_EXECUTION_ENABLED`) 동시 충족 + 격리 |
| 20 | 운영 환경에서 Claude Code 또는 LLM이 실계좌 주문 권한을 갖지 않게 한다. | 운영 원칙 문서화, secret 미열람, 권한 최소화 |

---

## 3. 전체 시스템 구조와 데이터 흐름

### 3.1 종단 간 파이프라인

```
외부 데이터 소스
  → 데이터 수집 및 정규화 (typed adapters)
  → Raw Evidence Store
  → Time-series Store
  → Feature Engineering
  → 정량 신호 엔진 (QuantFeature / Signal)
  → 분석 에이전트 (LLM, AgentRun → AgentFinding)
  → Market Regime Engine (9국면 분류)
  → Strategy Engine (StrategyVersion)
  → deterministic Risk Engine (LLM 미사용, deny-by-default)
  → Order Proposal
  → 사용자 승인 또는 정책 승인
  → Execution Gateway (격리 서비스)
  → 증권사 Open API
  → 체결 확인
  → 포지션 및 잔고 대사
  → Audit Log
```

### 3.2 LLM 영역 / 비LLM 영역 경계

이 경계는 안전의 핵심이다. **금융 계산과 주문 결정은 절대 LLM이 하지 않는다.**

| 영역 | 담당 | 책임 |
|------|------|------|
| **LLM 영역** | `agent-service`, `domain/agents` | 뉴스·공시·거시·수급·섹터·종목 분석 / 근거·반대 근거·불확실성·영향도 산출 / Trade Proposal(`OrderProposal`) 생성 |
| **비LLM 영역** | `execution-gateway`, `domain/risk`, `domain/execution`, `domain/money` | 가격 계산 / 포지션 계산 / 수량 계산 / 리스크 검증 / 주문 승인 / 주문 제출 / 체결 대사 / 손익 계산 / Kill Switch |

경계의 구조적 보장:
- `agent-service`와 `domain/agents` 소스에는 `submit_order` 임포트 경로가 존재하지 않는다(AST/문자열 스캔 테스트로 검증).
- `OrderProposal`(LLM 산출물)은 APPROVED `RiskDecision` 없이는 `ApprovedOrder`가 될 수 없다(팩토리에서 raise).
- `RiskDecision`은 오직 Risk Engine만 생성한다. `ApprovedOrder` 생성·broker 주문 메서드 호출은 오직 Execution Gateway만 가능하다.

---

## 4. 기술 스택과 확정 오버레이

### 4.1 권장 기술 스택 (스펙 §4)

| 영역 | 구성 |
|------|------|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zod, TradingView Lightweight Charts 또는 ECharts |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic, httpx |
| Database | PostgreSQL, TimescaleDB 확장 가능 구조, pgvector 확장 가능 구조 |
| Queue/Cache | Redis |
| Agent Runtime | Anthropic API, Structured JSON Output, Tool Use, Prompt Caching, 자체 오케스트레이터 |
| Testing | pytest, mypy, ruff, ESLint, TypeScript typecheck, frontend unit tests |
| Deployment | Docker Compose, 고정 도메인, Cloudflare Named Tunnel, Cloudflare Access, Secret Manager |
| Observability | 구조화 JSON 로그, OpenTelemetry / Prometheus / Grafana / Sentry 확장 가능 구조 |

### 4.2 확정 결정 오버레이 (이 장비/이번 빌드 적용 — 스펙보다 우선)

환경: Windows 11 / PowerShell / Node v24.15.0 / npm 11.12.1 / Python 3.14.4 / git 2.54.
**Docker · PostgreSQL · Redis · pnpm 은 이 장비에 설치돼 있지 않다.**

| 항목 | 확정 결정 | 근거 ADR |
|------|-----------|----------|
| 무도커 로컬 모드 | 스펙 전체 채택 + 로컬은 Docker 없이 동작 | ADR-012 |
| DB 전환 | `DATABASE_URL` 한 줄로 전환. 로컬/CI 기본 = SQLite(`aiosqlite`), 프로드/Docker = Postgres(`asyncpg`) | ADR-003, ADR-012 |
| asyncpg | **prod-only / optional.** 로컬에 설치 강제하지 않음 | ADR-012 |
| Redis 폴백 | 미설정/미가동 시 **fakeredis 폴백** + 상태 정직 보고. docker-compose에는 실제 redis | ADR-012 |
| Alembic 단일 마이그레이션 | SQLite·Postgres 양립. JSONB/네이티브 UUID 회피, `Numeric`·`DateTime(timezone=True)`·`JSON`·`String` 사용 | ADR-003 |
| worker | **APScheduler** (Celery/Redis 브로커 아님) | ADR-012 |
| 프런트 패키징 | **npm workspaces** (pnpm 없음) | ADR-012 |
| 백엔드 패키징 | 단일 venv + **src-layout 패키지 `kospi_watcher`** + `pyproject.toml`(ruff/mypy/pytest) + `requirements*.txt`(하한 핀, Python 3.14). `pip install -e .` editable 설치 | ADR-011 |
| Docker 검증 | `docker-compose.yml` + 서비스별 `Dockerfile`은 **작성**하되, 이 장비에 Docker 미설치 → `docker compose up`은 **실행/검증하지 않음**("미검증" 정직 명시) | ADR-012 |
| 금융 계산 | money/price는 **Decimal**(SQLAlchemy `Numeric`, Pydantic `Decimal`). float 금지 | ADR-008 |
| mock 정직성 | 실거래·실 브로커·실 Anthropic 호출·실 시장데이터 없음. mock을 실데이터로 위장 금지 | — |

---

## 5. 5개 서비스 책임

| 서비스 | 진입점(apps/) | 책임 | 주문 권한 |
|--------|---------------|------|-----------|
| **web** | `apps/web` | 사용자 대시보드, 시장 데이터 화면, 에이전트 분석 화면, 전략·백테스트 화면, 계좌·주문 화면, 관리자 화면 | 없음 |
| **api** | `apps/api` | 외부·내부 API, 인증, 조회 API, 도메인 서비스 진입점 | 없음(조회/검증) |
| **worker** | `apps/worker` | 데이터 수집, 예약 작업, 비동기 처리, 에이전트 실행 스케줄링(APScheduler) | 없음 |
| **agent-service** | `apps/agent-service` | 분석 에이전트 실행, Structured Output 검증, 근거·반대 근거 생성, Trade Proposal 생성. **주문 실행 권한 없음** | 없음(`OrderProposal`까지) |
| **execution-gateway** | `apps/execution-gateway` | 향후 브로커 연결을 위한 **격리 서비스**. 현재 Phase에서는 실제 주문 기능 구현 금지, 인터페이스와 안전한 mock만. Agent Service에서 직접 접근 불가하게 설계 | **유일하게** broker 주문 메서드 호출 가능(현재 mock) |

`apps/<svc>`는 얇은 진입점 + Docker 빌드 컨텍스트(ADR-011)다. 실제 도메인 로직은 `src/kospi_watcher/` 단일 설치형 패키지에 위치한다.

---

## 6. 최종 정보 구조 — 10개 메뉴 (요약)

Phase 0/1에서는 이 메뉴를 **모두 구현하지 않고** 문서와 기본 라우트 및 확장 가능한 구조만 설계한다.

| # | 메뉴 | 핵심 내용(요약) |
|---|------|-----------------|
| 1 | 오늘 | KOSPI/KOSPI200/KOSDAQ, 환율·금리·원자재, 글로벌 지수, 투자자 수급, 프로그램 매매, 시장 폭, 주도 업종·종목, 당일 핵심 뉴스, 시장 국면, 1·5·20일 전망, 포지션·주문 상태 |
| 2 | 실시간 시장 국면 | 9개 Regime(아래 §7.3) 분류 결과 |
| 3 | 거시·국제정세 | 한국 성장·물가·고용·소비·수출, 한국은행, 미 연준·글로벌 유동성, 중국 경기, 환율, 무역분쟁, 전쟁·제재, 공급망, 유가·원자재 |
| 4 | 수급·기술적 분석 | 투자자별 수급, 프로그램 매매, 선물 베이시스, 공매도·대차, 거래대금, 시장 폭, 신고가·신저가, 변동성, 추세, 모멘텀, 평균회귀, ETF 괴리율·iNAV |
| 5 | 섹터 | 수익률, 거래대금, 외국인·기관 수급, 이익 추정치 변화, 밸류에이션, 뉴스 모멘텀, 정책 수혜도, 수출·환율·원자재 민감도, 구조적 성장성, 단기 과열도 |
| 6 | 종목 | 기업 개요, 재무·실적, 최근 공시, 주요 뉴스, 섹터 내 상대 강도, 수급, 밸류에이션, 상승·하락 논거, 주요 촉매, 투자 논거 무효화 조건 |
| 7 | 구조적 성장 산업 | AI·반도체, 전력망·전력기기, 원전, 로봇·자동화, 방산·우주항공, 조선·해양, 바이오·의료기기, 배터리·소재, 친환경 에너지, 금융 인프라, 콘텐츠·플랫폼, 데이터센터 인프라, 공급망 국산화 |
| 8 | 트레이딩 랩 | 전략 정의, 조건식, 백테스트, 워크포워드 검증, 모의거래, 실시간 신호, 주문 제안, 전략 버전 관리 |
| 9 | 계좌와 체결 | 총자산, 현금, 보유종목, 평균단가, 실현·미실현 손익, 미체결 주문, 주문 이력, 전략별 손익, 리스크 사용량, Kill Switch |
| 10 | 관리자 | 데이터 소스 상태, 에이전트 상태, 모델·프롬프트 버전, 전략 버전, 리스크 한도, API 호출량, 비용, 장애 기록, Audit Log |

### 6.1 Phase 1 실제 구현 웹 화면 5개

| 라우트 | 내용 |
|--------|------|
| `/` | KOSPI-WATCHER 소개, 현재 운용 모드, **LIVE TRADING DISABLED** 표시, 시스템 상태, 향후 메뉴 구조 |
| `/dashboard` | placeholder 대시보드, 실제 금융 데이터 없음 명시, mock을 실데이터로 표시하지 않음 |
| `/agents` | 등록된 mock agent 목록, agent schema 예시, mock 실행 결과 |
| `/risk` | Risk Engine 설명, deny-by-default 상태, 테스트 Proposal 입력·평가 UI, **실제 주문 버튼 없음** |
| `/system` | API/DB/Redis 상태, 앱 버전, 환경, trading mode, live trading disabled 상태 |

UI는 깔끔하고 정돈된 금융 대시보드 스타일. 불필요한 배경사진·장식 이미지 금지.

---

## 7. 21개 에이전트 개요

### 7.1 에이전트 목록

| # | Agent | 역할 분류 |
|---|-------|-----------|
| 1 | Market Data Integrity Agent | 데이터 무결성 |
| 2 | News Deduplication Agent | 뉴스 처리 |
| 3 | Source Verification Agent | 출처 검증 |
| 4 | Disclosure & Corporate Event Agent | 공시·기업 이벤트 |
| 5 | Korea Macro Agent | 거시 |
| 6 | Global Growth Agent | 거시 |
| 7 | Rates & Liquidity Agent | 금리·유동성 |
| 8 | FX Agent | 환율 |
| 9 | Commodity & Energy Agent | 원자재·에너지 |
| 10 | Geopolitics & Trade Agent | 국제정세·무역 |
| 11 | Foreign & Institutional Flow Agent | 수급 |
| 12 | Derivatives & Program Agent | 파생·프로그램 |
| 13 | Breadth & Technical Agent | 기술적·시장 폭 |
| 14 | Volatility & Regime Agent | 변동성·국면 |
| 15 | Earnings & Valuation Agent | 실적·밸류에이션 |
| 16 | Technology & Semiconductor Agent | 섹터 |
| 17 | Industrial & Export Agent | 섹터 |
| 18 | Domestic Demand & Defensive Agent | 섹터 |
| 19 | Structural Growth Scout | 구조적 성장 탐색 |
| 20 | Red-Team & Risk Agent | 반대 논거·리스크 |
| 21 | Chief Market Synthesizer | 종합 |

### 7.2 Phase 0/1 범위 (에이전트)

실제 Anthropic API 호출은 구현하지 않고 다음만 수행한다.

- 공통 에이전트 인터페이스 설계
- `AgentFinding` Pydantic 모델 작성
- `AgentRun` 모델 작성
- 버전이 있는 JSON Schema 작성
- mock agent 구현
- validation test 작성
- Agent Service가 주문 실행 코드에 접근할 수 없음을 **구조적으로 보장**

### 7.3 9개 시장 국면(Market Regime)

`RISK_ON_STRONG` / `RISK_ON_FRAGILE` / `LIQUIDITY_RALLY` / `EARNINGS_RALLY` / `SIDEWAYS_LOW_VOL` / `SIDEWAYS_HIGH_VOL` / `RISK_OFF` / `CRISIS` / `DATA_UNCERTAIN`

### 7.4 AgentFinding 18필드

| 필드 | 의미 |
|------|------|
| `agent_name` | 에이전트 이름 |
| `agent_version` | 에이전트 버전 |
| `as_of` | 분석 기준 시점 |
| `horizon` | 전망 기간 |
| `direction` | 방향(상승/하락/중립 등) |
| `impact` | 영향도 |
| `confidence` | 확신도(impact와 구분) |
| `thesis` | 핵심 논거 |
| `evidence[]` | 근거(아래 Evidence 7필드) |
| `counterevidence[]` | 반대 근거 |
| `affected_sectors[]` | 영향 섹터 |
| `affected_symbols[]` | 영향 종목 |
| `invalidation_conditions[]` | 논거 무효화 조건 |
| `data_quality` | 데이터 품질 |
| `model_name` | 사용 모델 |
| `prompt_version` | 프롬프트 버전 |
| `created_at` | 생성 시각 |

### 7.5 Evidence 7필드

| 필드 | 필수 | 의미 |
|------|------|------|
| `source_id` | **필수** | 출처 식별자 |
| `source_type` | | 출처 종류 |
| `title` | | 제목 |
| `url` | | URL |
| `published_at` | | 발표 시각 |
| `available_at` | | 투자자 최초 인지 가능 시각 |
| `claim` | | 주장 |

**출처(`source_id`)가 없는 주장은 최종 점수에 반영하지 않는다.** 이 원칙을 문서화하고 모델 검증으로 강제한다(테스트 #3).

---

## 8. 데이터 시점 원칙

모든 데이터 모델은 다음 4개 시각을 구분할 수 있어야 한다.

| 시점 | 의미 |
|------|------|
| `event_time` | 실제 사건이 발생한 시각 |
| `published_at` | 외부 기관·언론이 발표한 시각 |
| `available_at` | 당시 투자자가 최초로 알 수 있었던 시각 |
| `ingested_at` | 시스템이 데이터를 수집한 시각 |

시간 원칙:

1. 모든 `datetime`은 **timezone-aware**여야 한다(naive 거부, 테스트 #2).
2. 내부 저장은 **UTC** 원칙.
3. 사용자 화면은 **Asia/Seoul** 기준 표시.
4. **point-in-time 백테스트**가 가능해야 한다.
5. **`available_at` 이후에만** 해당 데이터가 전략에서 사용될 수 있다(룩어헤드 금지).
6. 미래 데이터가 과거 백테스트에 유입되지 않도록 한다.

---

## 9. 핵심 도메인 모델 목록

다음 모델의 초안을 작성한다. 금액·가격·수량은 float 대신 **Decimal**. Enum을 적극 활용하되 DB↔API 직렬화 규칙을 명확히 정의한다.

| 분류 | 모델 |
|------|------|
| Instrument/세션 | `Instrument`, `TradingSession` |
| 시세 | `MarketBar`, `MarketTick`, `Quote`, `OrderBook`, `IndexSnapshot` |
| 수급/파생 | `InvestorFlow`, `ProgramTrade`, `ShortSellingStat` |
| 거시 | `MacroSeries`, `MacroObservation` |
| 뉴스/공시 | `NewsItem`, `NewsCluster`, `NewsClaim`, `Disclosure`, `FinancialStatement` |
| 섹터 | `Sector`, `SectorMembership`, `SectorSnapshot` |
| 에이전트 | `AgentRun`, `AgentFinding` |
| 신호/국면 | `MarketRegime`, `QuantFeature`, `Signal` |
| 전략/백테스트 | `Strategy`, `StrategyVersion`, `BacktestRun` |
| 리스크 | `RiskLimit`, `RiskDecision` |
| 주문/실행 | `OrderProposal`, `ApprovedOrder`, `Order`, `Execution` |
| 계좌 | `Position`, `AccountSnapshot` |
| 운영 | `Incident`, `AuditLog` |

---

## 10. Broker Adapter · Risk Engine · 주문 상태 머신 설계 요지

### 10.1 Broker Adapter

특정 증권사에 종속되지 않는 인터페이스를 설계한다. 인터페이스 메서드명은 **`submit_order(order: ApprovedOrder)`**다.

```python
class BrokerAdapter(Protocol):
    async def get_quote(self, symbol: str) -> Quote: ...
    async def get_orderbook(self, symbol: str) -> OrderBook: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_balance(self) -> AccountBalance: ...
    async def submit_order(self, order: ApprovedOrder) -> BrokerOrder: ...
    async def cancel_order(self, order_id: str) -> None: ...
    async def get_executions(self) -> list[Execution]: ...
```

Phase 0/1 구현 범위:
- `BrokerAdapter` Protocol
- `MockBrokerAdapter` (실제 주문을 수행하지 않는 안전한 stub)
- Agent Service가 `submit_order`를 import·호출하지 못하게 하는 테스트(테스트 #8)
- 향후 KIS와 Kiwoom Adapter를 추가할 수 있는 구조

**실제 한국투자증권·키움증권 API 연결은 구현하지 않는다.** `submit_order` 구현은 `domain/execution/broker` + `apps/execution-gateway`에만 둔다.

### 10.2 Risk Engine

Risk Engine은 **순수 코드**로 구현하며 **LLM을 사용하지 않는다.** 정책은 **deny-by-default** — 명시적으로 승인되지 않은 주문은 모두 거절.

최종적으로 수행할 검사(전체): 허용 종목 / 허용 전략 / 시장 개장 상태 / 데이터 최신성 / 호가 최신성 / 주문 가격 이탈 / 최대 주문 금액 / 최대 포지션 / 최대 총노출 / 일일 손실 한도 / 누적 낙폭 한도 / 전략별 손실 한도 / 일일 거래 횟수 / 슬리피지 한도 / 미체결 주문 수 / 계좌 대사 상태 / 중복 주문 / 변동성 급등 / API 장애 / 데이터 신뢰도 / ETF 괴리율 / iNAV 이상.

Phase 0/1 구현 범위:
- `RiskEngine` 인터페이스
- `RiskDecision` 모델
- 기본 deny-by-default 정책(미등록 종목 거절 — 테스트 #5)
- 테스트용 최소 규칙
- `risk_limits.yml` 초안
- 리스크 변경 시 ADR 또는 변경 로그 필요
- 실제 계좌 주문 기능 없음

**Kill Switch** 작동 조건(최종): 계좌 대사 불일치 / 중복 주문 감지 / 일일 손실 한도 초과 / 가격 데이터 지연 / 브로커 API 연속 오류 / 비정상 주문 수량 / 전략 버전 불일치 / 운영자의 긴급 중지.

### 10.3 주문 상태 머신 13상태

```
PROPOSED → RISK_REJECTED
PROPOSED → RISK_APPROVED → AWAITING_HUMAN → APPROVED → SUBMITTING → SUBMITTED
SUBMITTED → PARTIALLY_FILLED → FILLED
SUBMITTED / PARTIALLY_FILLED → CANCEL_PENDING → CANCELLED
(broker 거부) → REJECTED
(대사 불일치) → RECONCILIATION_ERROR
```

| 상태 | 의미 |
|------|------|
| `PROPOSED` | LLM/전략이 제안한 초기 상태 |
| `RISK_REJECTED` | Risk Engine 거절(종착) |
| `RISK_APPROVED` | Risk Engine 승인 |
| `AWAITING_HUMAN` | 사용자 승인 대기(GUARDED_LIVE) |
| `APPROVED` | 최종 승인(`ApprovedOrder` 생성 가능) |
| `SUBMITTING` | 제출 중 |
| `SUBMITTED` | 브로커 접수 |
| `PARTIALLY_FILLED` | 부분 체결 |
| `FILLED` | 전량 체결(종착) |
| `CANCEL_PENDING` | 취소 요청 중 |
| `CANCELLED` | 취소 완료(종착) |
| `REJECTED` | 브로커 거부(종착) |
| `RECONCILIATION_ERROR` | 대사 불일치(이상 상태) |

허용되는 상태 전이를 코드와 문서로 명시하고, **잘못된 상태 전이는 예외를 발생**시킨다(테스트 #9). `ApprovedOrder`는 APPROVED 상태의 `RiskDecision` 없이는 생성 불가(팩토리에서 raise, 테스트 #4). 중복 `idempotency_key` 주문은 거부한다(테스트 #10). Phase 0/1에서는 실제 주문 제출 없이 상태 머신과 단위 테스트만 작성한다.

---

## 11. DB · 보안 원칙

### 11.1 데이터베이스 설계

전체 고려 테이블: `instruments`, `trading_sessions`, `market_bars`, `news_items`, `disclosures`, `agent_runs`, `agent_findings`, `market_regimes`, `signals`, `strategy_versions`, `risk_limits`, `risk_decisions`, `order_proposals`, `orders`, `executions`, `positions`, `incidents`, `audit_logs`.

**Phase 1 우선 6테이블:**

| 테이블 | 용도 |
|--------|------|
| `instruments` | 종목/지수 마스터 |
| `agent_runs` | 에이전트 실행 기록 |
| `agent_findings` | 에이전트 산출물(18필드) |
| `risk_decisions` | Risk Engine 판정 |
| `order_proposals` | 주문 제안 |
| `audit_logs` | 감사 로그 |

Alembic migration을 작성하고 가능한 한 **reversible**해야 한다. 단일 마이그레이션은 SQLite·Postgres 양립을 위해 JSONB/네이티브 UUID를 회피하고 `Numeric`·`DateTime(timezone=True)`·`JSON`·`String`을 사용한다(테스트 #12).

### 11.2 보안 원칙 15개

1. `.env` 파일은 Git에 포함하지 않는다.
2. `.env.example`에는 변수명만 둔다(값 없음).
3. 비밀값을 로그에 출력하지 않는다.
4. API 응답에 내부 비밀값을 포함하지 않는다.
5. 웹 클라이언트에 브로커 키를 전달하지 않는다.
6. 입력값 검증을 적용한다.
7. SQL injection을 방지한다(파라미터 바인딩/ORM).
8. CORS 기본값을 제한적으로 설정한다.
9. 서비스 간 권한을 최소화한다.
10. Agent Service와 Execution Gateway를 네트워크 수준에서도 분리할 수 있게 한다.
11. Audit Log는 일반 애플리케이션 흐름에서 임의 삭제할 수 없도록 설계한다.
12. 실거래 관련 설정 변경은 별도 감사 로그 대상이다.
13. 운영용 키와 모의투자 키를 분리한다.
14. PAPER와 LIVE 환경을 분리한다.
15. production secret을 Claude Code가 읽거나 출력하지 못한다는 운영 원칙을 문서화한다.

### 11.3 `.env.example` 변수(값 없음)

```
APP_ENV=development
APP_NAME=KOSPI-WATCHER

DATABASE_URL=
REDIS_URL=

ANTHROPIC_API_KEY=

KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_NUMBER=

KIWOOM_APP_KEY=
KIWOOM_APP_SECRET=

DART_API_KEY=
ECOS_API_KEY=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

TRADING_MODE=RESEARCH
LIVE_TRADING_ENABLED=false
AUTO_EXECUTION_ENABLED=false
```

---

## 12. 디렉터리 구조 (src-layout 반영)

오버레이 D/F항에 따라 백엔드 도메인 로직은 src-layout 단일 설치형 패키지 `kospi_watcher`에 둔다. `apps/<svc>`는 얇은 진입점 + Docker 빌드 컨텍스트다(ADR-011). 변경 이유는 ADR-011/012에 기록.

```
kospi-watcher/
├── CLAUDE.md
├── README.md
├── docker-compose.yml
├── pyproject.toml                  # ruff/mypy/pytest, 패키지 kospi_watcher
├── requirements.txt                # 하한 핀(Python 3.14)
├── requirements-dev.txt
├── .env.example                    # 변수명만, 값 없음
├── .gitignore
├── apps/                           # 얇은 진입점 + Docker 빌드 컨텍스트
│   ├── web/                        # Next.js (npm workspaces)
│   ├── api/
│   ├── worker/                     # APScheduler
│   ├── agent-service/
│   └── execution-gateway/
├── packages/                       # 프런트 공유(npm workspaces)
│   ├── schemas/
│   ├── ui/
│   ├── config/
│   └── generated-client/
├── src/
│   └── kospi_watcher/              # 단일 설치형 백엔드 패키지 (pip install -e .)
│       ├── config.py
│       ├── logging.py
│       ├── infrastructure/
│       │   ├── db/                 # SQLAlchemy engine/session (aiosqlite | asyncpg)
│       │   └── redis/              # Redis + fakeredis 폴백
│       ├── domain/
│       │   ├── time/               # tz-aware, UTC, available_at
│       │   ├── money/              # Decimal
│       │   ├── enums/              # modes, regimes, order states
│       │   ├── agents/             # AgentFinding/AgentRun/Evidence, 공통 인터페이스
│       │   ├── risk/               # deny-by-default RiskEngine, RiskDecision
│       │   ├── execution/          # 상태 머신, ApprovedOrder, broker(submit_order)
│       │   ├── market/
│       │   ├── news/
│       │   ├── macro/
│       │   └── strategies/
│       ├── db/                     # ORM 모델
│       ├── api/
│       │   ├── app.py
│       │   ├── routes/
│       │   └── schemas/
│       ├── agent_service/          # submit_order 임포트 경로 없음
│       ├── execution_gateway/
│       └── worker/
├── config/
│   ├── agents/
│   ├── strategies/
│   ├── instruments.yml
│   └── risk_limits.yml
├── prompts/
│   ├── system/
│   ├── agents/
│   └── evaluations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── backtest/
│   └── security/
├── docs/
│   ├── ULTRAPLAN.md
│   ├── PRODUCT_SPEC.md
│   ├── ARCHITECTURE.md
│   ├── DATA_DICTIONARY.md
│   ├── AGENT_DESIGN.md
│   ├── TRADING_SAFETY.md
│   ├── THREAT_MODEL.md
│   ├── RUNBOOK.md
│   └── adr/                        # ADR-001 ~ ADR-012
├── infra/
│   ├── docker/
│   ├── cloudflare/
│   ├── monitoring/
│   └── backup/
└── alembic/                        # SQLite·Postgres 양립 단일 마이그레이션
```

---

## 13. Phase 0 범위와 완료 기준

### 13.1 범위 (설계·정책 문서)

작성 문서 8종: `ULTRAPLAN`(본 문서), `PRODUCT_SPEC`, `ARCHITECTURE`, `TRADING_SAFETY`, `THREAT_MODEL`, `DATA_DICTIONARY`, `AGENT_DESIGN`, `RUNBOOK`.

ADR 12종:

| ADR | 주제 |
|-----|------|
| ADR-001 | LLM Agent와 주문 실행 계층 분리 |
| ADR-002 | Broker Adapter 추상화 |
| ADR-003 | PostgreSQL 및 TimescaleDB 확장 구조 선택(+ SQLite/Postgres 양립) |
| ADR-004 | 에이전트 Structured Output 사용 |
| ADR-005 | PAPER와 LIVE 환경 분리 |
| ADR-006 | Audit Log 불변성 원칙 |
| ADR-007 | Cloudflare 운영 배포 정책 |
| ADR-008 | Decimal 기반 금융 계산 |
| ADR-009 | point-in-time 데이터 모델 |
| ADR-010 | deny-by-default Risk Engine |
| ADR-011 | 모노레포 src-layout(`src/kospi_watcher`) 패키징 결정 |
| ADR-012 | npm workspaces + 단일 venv 툴체인, asyncpg prod-only, Redis fakeredis 폴백 결정 |

각 ADR 형식: **Status / Context / Decision / Consequences / Alternatives Considered.**
추가 산출물: `CLAUDE.md`(루트), `.env.example`(변수명만).

### 13.2 완료 기준

- 필수 설계 문서 8종 존재
- 필수 ADR 12종 존재
- `CLAUDE.md` 존재
- 실거래 안전 원칙 명시
- LLM과 주문 실행 경계 명시
- point-in-time 데이터 원칙 명시
- Risk Engine deny-by-default 원칙 명시

---

## 14. Phase 1 범위와 완료 기준

### 14.1 범위 (기반 구현)

구현 순서(오버레이 G항):
1. **Step 0 디리스크**: 폴더/venv/패키지 설치(asyncpg 제외) · src-layout 임포트 스모크 pytest · `next build` 1회 통과.
2. 인프라: `config` / `logging` / `db`(aiosqlite|asyncpg) / `redis`(fakeredis 폴백).
3. 도메인: `time` / `money`(Decimal) / `enums` + `AgentFinding`·`Evidence`(`source_id` 필수).
4. DB ORM 6테이블(`instruments`, `agent_runs`, `agent_findings`, `risk_decisions`, `order_proposals`, `audit_logs`) + Alembic.
5. Risk Engine(deny-by-default).
6. 브로커 격리 + 주문 상태 머신(13상태, 불법 전이 raise).
7. mock 21에이전트 레지스트리.
8. API 7엔드포인트.
9. Next.js 5페이지.
10. worker(APScheduler).
11. docker-compose / Dockerfile / infra.
12. 테스트 15(스펙 §22) + CI.

**API 7개:**

| 메서드/경로 | 책임 |
|-------------|------|
| `GET /health` | API/DB/Redis 상태, trading mode, live trading enabled 여부(비밀값 미반환) |
| `GET /api/v1/system/status` | 서비스 버전, 환경, 서버 시각, trading mode, 기능 플래그, 데이터 소스 상태 placeholder |
| `GET /api/v1/agents` | 등록된 mock agent 목록(이름/버전/활성화 여부) |
| `POST /api/v1/agents/mock-run` | mock agent 실행, `AgentFinding` Schema 검증, 실제 Anthropic 호출 없음 |
| `POST /api/v1/order-proposals/validate` | `OrderProposal` Schema 검증, 실제 주문 없음 |
| `POST /api/v1/risk/evaluate` | deny-by-default Risk Engine 실행, 테스트 Proposal 승인/거절, 실제 주문 없음 |
| `GET /api/v1/audit-logs` | 개발용 Audit Log 조회, pagination, 민감정보 제외 |

**웹 5페이지:** `/`, `/dashboard`, `/agents`, `/risk`, `/system` (§6.1).

**테스트 15개(스펙 §22):**

| # | 테스트 |
|---|--------|
| 1 | Money/Price에 float가 사용되지 않는지 |
| 2 | timezone-naive datetime이 거부되는지 |
| 3 | `AgentFinding`이 필수 `source_id` 없이 evidence를 허용하지 않는지 |
| 4 | `OrderProposal`이 `RiskDecision` 없이 `ApprovedOrder`가 될 수 없는지 |
| 5 | deny-by-default Risk Engine이 미등록 종목을 거절하는지 |
| 6 | `LIVE_TRADING_ENABLED`가 기본 false인지 |
| 7 | `AUTO_EXECUTION_ENABLED`가 기본 false인지 |
| 8 | Agent Service가 `BrokerAdapter.submit_order`에 접근하지 못하는지 |
| 9 | 잘못된 주문 상태 전이가 거부되는지 |
| 10 | 동일 `idempotency_key`의 중복 주문을 거부하는지 |
| 11 | 비밀값이 API 응답과 로그에서 노출되지 않는지 |
| 12 | DB migration이 정상 작동하는지 |
| 13 | Health Check가 DB와 Redis 상태를 올바르게 반환하는지 |
| 14 | `AgentFinding` JSON Schema가 정상 생성되는지 |
| 15 | Audit Log가 중요 상태 변경을 기록하는지 |

**검증 게이트(오버레이 H항, 로컬 실제 실행):** `ruff check` · `mypy` · `pytest` · (web) `eslint` · `tsc --noEmit` · `next build` · `alembic upgrade head`(sqlite)→`downgrade base`. **`docker compose up` = 미검증 명시.**

### 14.2 완료 기준

- Docker Compose로 개발 환경 실행 가능 — **단, 오버레이 C: 본 장비 Docker 미설치 → 이 항목만 "미검증"으로 명시**
- API·Web·DB·Redis 연결
- 모든 서비스 health check
- 핵심 도메인 모델
- `AgentFinding` Schema
- `BrokerAdapter` · `MockBrokerAdapter`
- deterministic Risk Engine 기본 구조
- 주문 상태 머신
- 최소 API 7개
- 최소 프런트엔드 화면 5개
- Alembic migration
- 테스트 통과 / lint 통과 / typecheck 통과 / frontend build 통과
- 실제 실거래 기능 없음
- mock 금융 데이터가 실제 데이터로 오인되지 않음
- 비밀값이 코드나 로그에 없음

---

## 15. Phase 2+ 로드맵

Phase 2 이상은 이번 빌드에서 **구현하지 않는다.** 향후 단계의 방향만 기록한다.

| 영역 | Phase 2+ 권장 작업 |
|------|--------------------|
| 데이터 | 실제 외부 어댑터 연동(DART, ECOS, FRED, 뉴스), Raw Evidence Store, Time-series Store, TimescaleDB/pgvector 실사용 |
| 에이전트 | 실제 Anthropic API 호출, Structured Output/Tool Use/Prompt Caching, 21에이전트 실프롬프트, 에이전트 평가 파이프라인 |
| 엔진 | Feature Engineering, 정량 신호 엔진, Market Regime Engine 실로직, Strategy Engine, Backtest/워크포워드 |
| 리스크 | Risk Engine 전체 검사 항목 구현, Kill Switch 실작동, 리스크 사용량 추적 |
| 실행 | KIS/Kiwoom Adapter 실연동(명세 확정 후), PAPER 모의체결, GUARDED_LIVE 승인 플로우, 체결·잔고 대사 |
| 운영 | Cloudflare Named Tunnel/Access, Secret Manager, OpenTelemetry/Prometheus/Grafana/Sentry, 고정 도메인 배포 |
| 정보구조 | 10개 메뉴 전체 화면 구현 |

실거래(`LIVE_TRADING_ENABLED`/`AUTO_EXECUTION_ENABLED`) 활성화는 명시적 별도 요청 + 안전 검증 통과 후에만 진행한다.

---

## 16. 위험 요소와 가정

### 16.1 위험 요소

| 위험 | 영향 | 완화 |
|------|------|------|
| Python 3.14 휠 부재(특히 asyncpg/네이티브 빌드) | 설치 실패 | Step 0에서 로컬 세트(asyncpg 제외) 먼저 설치, asyncpg는 prod-only/optional |
| Docker 미설치로 compose 미검증 | 통합 동작 미확인 | 작성만 하고 "미검증(Docker 미설치)" 정직 명시, SQLite/fakeredis로 로컬 대체 검증 |
| SQLite↔Postgres 마이그레이션 비양립(JSONB/UUID) | 마이그레이션 실패 | JSONB/네이티브 UUID 회피, `Numeric`/`DateTime(tz)`/`JSON`/`String` 사용 |
| 경계 침범(Agent가 `submit_order` 접근) | 안전 불변식 위반 | 패키지 격리 + AST/문자열 스캔 테스트(테스트 #8) |
| mock을 실데이터로 오인 | 잘못된 의사결정 | "MOCK DATA — NOT REAL MARKET DATA" 배너 + 화면 명시 |
| 비밀값 노출(로그/API/프런트) | 자격증명 유출 | secret 마스킹, `.env.example` 변수명만, API 응답 제외(테스트 #11) |
| 룩어헤드 바이어스 | 백테스트 신뢰성 훼손 | `available_at` 이후만 사용, point-in-time 모델 |
| 외부 API 명세 불확실(KIS/Kiwoom) | 잘못된 구현 | 추측 구현 금지(§2-17), 실연동 미구현·mock stub만 |
| float 사용으로 금융 오차 | 금액 정확성 훼손 | Decimal 강제(SQLAlchemy `Numeric`/Pydantic `Decimal`, 테스트 #1) |

### 16.2 가정

- 현재 작업 디렉터리 `C:\Users\andul\kospi-watcher`가 의도된 프로젝트 루트이며, `_KICKOFF.md`는 지시문이므로 빈 디렉터리로 간주한다(이중 중첩 금지).
- 환경은 Windows 11 / PowerShell / Node v24.15.0 / npm 11.12.1 / Python 3.14.4 / git 2.54.
- Docker · PostgreSQL · Redis · pnpm은 미설치이며, 로컬은 SQLite(aiosqlite) + fakeredis로 동작한다.
- 이번 빌드는 전부 mock이며 실거래·실 브로커·실 Anthropic 호출·실 시장데이터가 없다.
- `git init`은 하되 commit은 사용자가 요청하기 전까지 하지 않는다.
- 형제 프로젝트(`C:\Users\andul\krw-watcher`, `C:\Users\andul\fed-watcher`)는 수정하지 않는다.
- 사소한 선택은 합리적 기본값을 채택하고 ADR/보고서에 기록한다.
```
