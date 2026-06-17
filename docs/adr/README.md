# Architecture Decision Records (ADR)

이 디렉터리는 KOSPI-WATCHER의 주요 아키텍처 결정을 기록한 ADR 모음이다. 각 ADR은 되돌리기 어렵거나 시스템 전반에 영향을 주는 결정을, 그 맥락(Context)·결정(Decision)·결과(Consequences)·검토한 대안(Alternatives Considered)과 함께 남긴다.

## 작성 규칙

각 ADR은 `# ADR-00X: <제목>` 제목 다음에 **Status / Context / Decision / Consequences / Alternatives Considered** 다섯 절을 정확히 이 순서로 둔다. Status는 `Accepted (YYYY-MM-DD)` 형식이며, 한 번 Accepted된 ADR은 수정 대신 새 ADR로 대체(supersede)한다. 본문은 한국어, 기술용어·식별자·경로는 영어로 쓴다.

## 인덱스

| 번호 | 제목 | 상태 |
|------|------|------|
| [ADR-001](ADR-001-llm-execution-separation.md) | LLM Agent와 주문 실행 계층 분리 | Accepted (2026-06-17) |
| [ADR-002](ADR-002-broker-adapter-abstraction.md) | Broker Adapter 추상화 | Accepted (2026-06-17) |
| [ADR-003](ADR-003-postgresql-timescale.md) | PostgreSQL 및 TimescaleDB 확장 구조 선택 | Accepted (2026-06-17) |
| [ADR-004](ADR-004-agent-structured-output.md) | 에이전트 Structured Output 사용 | Accepted (2026-06-17) |
| [ADR-005](ADR-005-paper-live-separation.md) | PAPER와 LIVE 환경 분리 | Accepted (2026-06-17) |
| [ADR-006](ADR-006-audit-log-immutability.md) | Audit Log 불변성 원칙 | Accepted (2026-06-17) |
| [ADR-007](ADR-007-cloudflare-deployment.md) | Cloudflare Named Tunnel + Access 운영 배포 정책 | Accepted (2026-06-17) |
| [ADR-008](ADR-008-decimal-financial-math.md) | Decimal 기반 금융 계산 (float 금지) | Accepted (2026-06-17) |
| [ADR-009](ADR-009-point-in-time-data.md) | point-in-time 데이터 모델 (룩어헤드 방지) | Accepted (2026-06-17) |
| [ADR-010](ADR-010-deny-by-default-risk-engine.md) | deny-by-default Risk Engine | Accepted (2026-06-17) |
| [ADR-011](ADR-011-src-layout-packaging.md) | 모노레포 src-layout (src/kospi_watcher) 패키징 결정 | Accepted (2026-06-17) |
| [ADR-012](ADR-012-toolchain-local-mode.md) | 툴체인(npm workspaces + 단일 venv) 및 무도커 로컬모드 | Accepted (2026-06-17) |
| [ADR-013](ADR-013-market-data-yahoo.md) | 키리스 Yahoo Finance 시세 provider + mock 폴백 | Accepted (2026-06-17) |
| [ADR-014](ADR-014-paper-execution.md) | PAPER(모의) 실행을 안전한 실행 계층으로 구현 | Accepted (2026-06-17) |
| [ADR-015](ADR-015-llm-agent-runtime.md) | 실 LLM(Anthropic) 에이전트 런타임 + mock 폴백 | Accepted (2026-06-17) |
| [ADR-016](ADR-016-agent-org-hierarchy.md) | 계층형 리서치 데스크 조직 (5데스크+Chief·3티어·가중·리드) | Accepted (2026-06-17) |
| [ADR-017](ADR-017-prediction-and-brief.md) | 결정론적 예측 종합기 + 데일리 브리핑 + 롱/숏 스탠스(인버스/곱버스) | Accepted (2026-06-17) |
| [ADR-018](ADR-018-news-scraping.md) | 키리스 Google News RSS 스크랩 + defusedxml + 일자별·보존 정리 저장 + 뉴스 인지 브리핑 | Accepted (2026-06-17) |
| [ADR-019](ADR-019-deliberation-and-ui.md) | 에이전트 논의 가시화(데스크→수석 조율) + 모던 다중 페이지 UI + 면책·소유권 | Accepted (2026-06-17) |
| [ADR-020](ADR-020-news-daily-brief.md) | 뉴스 데일리 브리프(뉴스 라운드업)를 예측 리포트와 분리 | Accepted (2026-06-17) |
| [ADR-021](ADR-021-morning-briefing-telegram.md) | 08:00 Asia/Seoul 아침 브리핑 → Telegram 자동 전송 | Accepted (2026-06-17) |

> ADR-001~010은 원본 스펙 §17이 지정한 ADR이고, ADR-011·ADR-012는 킥오프 오버레이 F항에 따라 추가된 패키징·툴체인 결정이다. ADR-013~015는 시세·모의 실행·LLM 런타임 세 신규 기능 도입에 따른 결정이다. ADR-016·ADR-017은 제품 무게중심을 예측·데일리 브리핑으로 옮기며 도입한 계층형 데스크 조직과 결정론적 예측 종합기 결정이다. ADR-018·ADR-019는 데일리 브리핑을 뉴스 근거로 보강하고(키리스 뉴스 스크랩) 예측을 만든 에이전트 논의를 가시화하며 웹을 모던 다중 페이지 UI로 재설계한 결정이다. ADR-020·ADR-021은 뉴스 데일리 브리프를 예측 리포트와 별개의 뉴스 라운드업 아티팩트로 분리하고, 08:00 Asia/Seoul 아침 브리핑이 예측 리포트+뉴스 브리프를 Telegram으로 자동 전송하도록 한 결정이다.
