# ADR-003: PostgreSQL 및 TimescaleDB 확장 구조 선택

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 시장 시계열(MarketBar, MarketTick, IndexSnapshot), 수급(InvestorFlow, ProgramTrade), 거시(MacroObservation), 뉴스/공시, 에이전트 출력, 주문/체결/포지션, Audit Log 등 다양한 데이터를 저장한다. 이 중 상당수는 시간축이 핵심인 고빈도 시계열이며, point-in-time(ADR-009) 질의와 백테스트를 지원해야 한다. 또한 뉴스/공시 임베딩 기반 유사도 검색(pgvector) 확장 여지도 필요하다.

스펙 §4(권장 기술 스택)는 Database로 PostgreSQL, TimescaleDB 확장 가능 구조, pgvector 확장 가능 구조를 명시한다. 그러나 오버레이 A항은 이 개발 장비에 Docker·PostgreSQL·Redis가 설치돼 있지 않음을 명시하고, 오버레이 B항은 DB를 `DATABASE_URL` 한 줄로 전환(로컬/CI 기본 = SQLite/aiosqlite, 프로드/Docker = Postgres/asyncpg)하도록 한다. asyncpg는 prod-only/optional이다.

따라서 운영 타깃 RDBMS와 로컬 개발 RDBMS를 분리하되, 단일 스키마/마이그레이션이 양쪽에서 동작해야 한다.

## Decision

운영(프로드) 타깃 데이터베이스로 **PostgreSQL**을 선택하고, **TimescaleDB**(시계열 hypertable)와 **pgvector**(임베딩) 확장이 가능한 구조로 스키마를 설계한다. 로컬/CI 개발은 ADR-012의 SQLite로 보완한다(교차참조).

1. **프로드 = PostgreSQL.** SQLAlchemy + asyncpg(prod-only/optional)로 연결한다. 시계열 테이블은 TimescaleDB hypertable로 승격 가능하도록 시간 컬럼·파티션 키를 의식해 설계한다. 뉴스/공시 임베딩 컬럼은 향후 pgvector 타입으로 확장 가능하게 둔다.
2. **로컬/CI = SQLite.** `DATABASE_URL`이 SQLite(aiosqlite)를 가리키면 로컬에서 Postgres 없이 전 기능을 개발·테스트한다. asyncpg는 로컬에 설치 강제하지 않는다(ADR-012).
3. **단일 마이그레이션의 이식성.** Alembic 단일 마이그레이션이 SQLite·Postgres 양쪽에서 동작하도록, Postgres 전용 타입을 회피한다: JSONB 대신 `JSON`, 네이티브 UUID 대신 `String`, 금액/수량은 `Numeric`(ADR-008), 시각은 `DateTime(timezone=True)`(ADR-009)를 사용한다. TimescaleDB hypertable 전환·pgvector 인덱스는 Postgres 환경에서만 적용하는 선택적 마이그레이션 단계로 분리한다.
4. **Docker 미검증 명시.** docker-compose.yml의 postgres 서비스는 작성하되, 이 장비에 Docker 미설치이므로 `docker compose up`은 실행/검증하지 않고 보고서에 "미검증(Docker 미설치)"로 정직히 기재한다(오버레이 C).

## Consequences

- 운영에서 PostgreSQL+TimescaleDB의 시계열 성능과 SQL 생태계를 확보하고, pgvector로 의미 검색까지 확장할 길을 연다.
- 로컬/CI는 SQLite로 가볍고 빠르게 돌아, 개발자가 무거운 인프라 없이 전 흐름을 재현할 수 있다.
- 단일 마이그레이션 이식성을 위해 JSONB/native UUID/배열형 등 Postgres 고유 기능을 1차적으로 포기한다. JSONB 인덱싱·서버사이드 UUID 생성 같은 이점은 프로드 전용 선택적 마이그레이션으로만 도입한다.
- SQLite와 Postgres의 타입/제약 차이(예: 외래키 강제, 동시성)가 미묘한 차이를 만들 수 있어, CI에서 SQLite를, 그리고 가능 시 프로드 유사 환경에서 Postgres를 함께 검증하는 것이 바람직하다.
- `alembic upgrade head`(sqlite) → `downgrade base` 왕복을 로컬 검증 게이트로 둔다(오버레이 H).

## Alternatives Considered

- **시작부터 PostgreSQL 전용(rejected for local).** 로컬도 Postgres로 통일하면 prod parity가 가장 높다. 그러나 이 장비에 Postgres·Docker가 없고 설치를 강제하지 않는다는 제약(오버레이 A) 때문에 채택 불가. 대신 프로드 타깃으로만 둔다.
- **시계열 전용 DB(InfluxDB/ClickHouse)(rejected).** 고빈도 시계열엔 강하나, 주문·리스크·Audit 같은 관계형/트랜잭션 데이터와 한 시스템에서 ACID로 묶기 어렵고, 단일 마이그레이션 이식성·pgvector 결합을 잃는다. PostgreSQL+TimescaleDB가 관계형+시계열을 한 엔진에서 제공하므로 기각.
- **SQLite 단독 운영(rejected).** 로컬엔 충분하나, 운영 규모의 시계열·동시성·확장(Timescale/pgvector)을 감당하지 못한다. 따라서 로컬/CI 한정으로만 사용하고 프로드는 PostgreSQL로 둔다.
