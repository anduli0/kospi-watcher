# ADR-012: 툴체인(npm workspaces + 단일 venv) 및 무도커 로컬모드

## Status

Accepted (2026-06-17)

## Context

이 프로젝트는 다음 개발 장비에서 시작·검증된다: **Windows 11 / PowerShell / Node v24.15.0 / npm 11.12.1 / Python 3.14.4 / git 2.54.** 이 장비에는 **Docker · PostgreSQL · Redis · pnpm 이 설치돼 있지 않다**(오버레이 A). 스펙 §4는 운영 스택으로 PostgreSQL/Redis/Docker Compose를, 프런트 패키지 매니저로 npm 또는 pnpm을 언급한다. 그러나 로컬에 없는 인프라를 설치 강제하면 개발이 막히고, Python 3.14는 비교적 신규라 일부 패키지 휠(wheel) 가용성 문제가 있을 수 있다.

따라서 "스펙 전체 채택 + 무도커 로컬모드"(오버레이 B)를 실현할 툴체인·런타임 폴백 정책이 필요하다. 오버레이 B/D/G는 다음을 지시한다: 프런트는 npm workspaces(pnpm 없음); 백엔드는 단일 venv + src-layout 패키지 `kospi_watcher`(ADR-011) + `pyproject.toml` + `requirements.txt`/`requirements-dev.txt`(하한 핀, Python 3.14); `pip install -e .`; DB는 `DATABASE_URL`로 전환(로컬/CI 기본 SQLite/aiosqlite, 프로드/Docker Postgres/asyncpg, asyncpg prod-only/optional); Redis 미설정/미가동 시 fakeredis 폴백 + 상태 정직 보고; worker는 APScheduler; Step 0에서 venv 생성 후 로컬 세트(asyncpg 제외)부터 설치해 3.14 휠 문제를 먼저 제거.

## Decision

**npm workspaces(프런트) + 단일 venv(백엔드)** 툴체인을 채택하고, **무도커 로컬모드**를 기본으로 하여 SQLite/fakeredis로 폴백한다. asyncpg는 prod-only로 둔다.

1. **프런트 = npm workspaces.** 프런트엔드 모노레포는 npm workspaces로 구성한다(pnpm 미사용). `apps/web`(Next.js) 및 `packages/*`를 워크스페이스로 둔다.
2. **백엔드 = 단일 venv + src-layout.** 단일 venv에 `kospi_watcher` 패키지(ADR-011)를 `pip install -e .`로 editable 설치한다. `pyproject.toml`에 ruff/mypy/pytest 설정을, `requirements.txt`/`requirements-dev.txt`에 하한 핀(lower-bound pin, Python 3.14 기준) 의존성을 둔다.
3. **DB는 DATABASE_URL 전환 / asyncpg prod-only.** 로컬·CI 기본은 SQLite(aiosqlite). 프로드/Docker는 PostgreSQL(asyncpg). **asyncpg는 prod-only/optional**로, 로컬 설치를 강제하지 않는다(requirements-dev에 강제 포함하지 않음). 단일 Alembic 마이그레이션이 양립하도록 Postgres 전용 타입을 회피한다(ADR-003).
4. **Redis는 fakeredis 폴백.** Redis가 미설정/미가동이면 fakeredis로 폴백하고, health/status가 "실제 Redis 아님(fakeredis)"임을 정직히 보고한다. docker-compose에는 실제 redis 서비스를 둔다.
5. **worker = APScheduler.** 예약 작업은 APScheduler로 구현한다(Celery/Redis 브로커 미사용).
6. **무도커 로컬모드 + 미검증 명시.** docker-compose.yml과 서비스별 Dockerfile은 작성하되, 이 장비에 Docker 미설치이므로 `docker compose up`을 실행/검증하지 않고 보고서에 "미검증(Docker 미설치)"로 정직히 명시한다(오버레이 C).
7. **Step 0 디리스크.** 폴더/venv 생성 → 로컬 세트(asyncpg 제외) 설치 → src-layout import 스모크 pytest → `next build` 1회 통과를 먼저 수행해 3.14 휠 문제와 패키징 문제를 조기에 제거한다.

## Consequences

- 개발자가 Docker·PostgreSQL·Redis 없이도 전 흐름(도메인·API·web·테스트)을 로컬에서 재현할 수 있다. 진입 장벽이 낮아진다.
- `DATABASE_URL` 한 줄과 Redis 폴백으로 로컬↔프로드 전환이 단순해진다. 프로드 의존성(asyncpg)이 로컬을 오염시키지 않는다.
- fakeredis/SQLite는 실제 Redis/Postgres와 미묘하게 다를 수 있다(동시성·기능·타입). 따라서 상태를 정직히 보고하고, 프로드 유사 환경에서의 추가 검증을 권장한다.
- Docker compose가 이 장비에서 미검증이므로, 운영 전 별도 환경에서 compose·Postgres·Redis를 실제 기동·검증해야 한다(정직한 한계 명시).
- 단일 venv + src-layout(ADR-011)로 모든 서비스가 동일 설치본을 공유해 일관성이 높아진다. 다만 기여자는 `pip install -e .`와 venv 활성화를 선행해야 한다(RUNBOOK 연계).
- 하한 핀은 최신 휠을 받기 쉬우나 재현성은 상한 고정보다 약하다. Python 3.14 신규성을 고려해 Step 0에서 설치 가능성을 먼저 확인하는 것으로 보완한다.

## Alternatives Considered

- **pnpm + Docker 필수(rejected).** 스펙이 pnpm을 언급하고 Docker Compose를 권장하나, 이 장비엔 둘 다 없고 설치를 강제하지 않는다(오버레이 A). npm workspaces + 무도커 로컬모드로 대체한다.
- **로컬도 PostgreSQL/Redis 강제(rejected).** prod parity는 높지만 미설치 장비에서 개발이 막힌다. `DATABASE_URL` 전환 + fakeredis 폴백으로 로컬을 가볍게 유지하고, 프로드 타깃만 Postgres/Redis로 둔다(ADR-003).
- **Celery + Redis 브로커로 스케줄링(considered, not chosen).** 분산 작업엔 강력하나 Redis 가동을 전제하고 이번 범위엔 과하다. Redis 폴백 정책과 충돌하므로 APScheduler로 시작한다.
- **상한 고정(upper-bound pin)/lockfile 우선(considered, not chosen).** 재현성은 높으나, Python 3.14 신규 환경에서 휠 미가용으로 설치가 막힐 위험이 크다. 하한 핀 + Step 0 설치 검증으로 시작하고, 안정화 후 lockfile 강화를 후속으로 둔다.
