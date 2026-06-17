# KOSPI-WATCHER — 운영 런북 (RUNBOOK)

이 문서는 KOSPI-WATCHER를 **이 장비(Windows 11 / PowerShell)** 에서 셋업하고, 실행하고, 점검하고, 장애에 대응하기 위한 실무 런북이다. 권위 있는 출처는 프로젝트 루트의 `_KICKOFF.md`(A 결정 오버레이 + B 스펙 전문, 특히 §16.8)이며, 본 문서의 모든 내용은 이와 일치한다.

> **운영 모드 캐논 (절대 변경 금지, 명시 요청 전까지)**
> - `TRADING_MODE=RESEARCH`
> - `LIVE_TRADING_ENABLED=false`
> - `AUTO_EXECUTION_ENABLED=false`
>
> LLM 에이전트는 브로커 주문 API를 **직접 호출할 수 없다.** 모든 주문은 deterministic Risk Engine의 승인을 거친다. 이 Phase의 모든 시장/금융 데이터는 **MOCK DATA — NOT REAL MARKET DATA** 다.

> **무도커 로컬모드 (이 장비)**
> 이 장비에는 **Docker · PostgreSQL · Redis · pnpm 이 설치돼 있지 않다.** 따라서 로컬에서는 DB = SQLite(`aiosqlite`), 캐시/큐 = `fakeredis` 폴백, worker = APScheduler 로 동작한다. Postgres/Redis는 `DATABASE_URL` / `REDIS_URL` 환경변수로만 전환한다.

> **문서 적용 시점에 대한 주의**
> 본 런북은 Phase 0/Phase 1의 **목표 운영 절차**를 기술한다. 일부 진입점·설정 파일(`apps/<svc>/main.py`, `.env.example`, `alembic.ini`, `docker-compose.yml`)은 Phase 1 구현이 진행되며 채워진다. 아래 명령은 캐논에 따른 정규 형태이며, 해당 산출물이 존재할 때 그대로 복붙해 사용한다.

---

## 1. 사전 준비물 · 버전

이 장비에 이미 설치되어 있어야 하는 도구와 검증된 버전이다.

| 구분 | 도구 | 버전 (이 장비 기준) | 비고 |
| --- | --- | --- | --- |
| OS | Windows 11 Home | 10.0.26200 | |
| Shell | PowerShell | 7+ (pwsh) 권장 | 모든 명령은 PowerShell 기준 |
| Runtime | Node.js | v24.15.0 | 프런트(Next.js) |
| Runtime | npm | 11.12.1 | **npm workspaces** (pnpm 미설치) |
| Runtime | Python | 3.14.4 | 백엔드 단일 venv |
| VCS | git | 2.54 | `git init`만, commit은 요청 시 |
| (미설치) | Docker | — | **이 장비 미설치** → `docker compose up` 미검증 |
| (미설치) | PostgreSQL | — | 로컬은 SQLite 사용 |
| (미설치) | Redis | — | 로컬은 fakeredis 폴백 |

설치 여부와 버전을 확인한다.

```powershell
node --version
npm --version
python --version
git --version
# Docker는 이 장비에 없음(있다면 미검증 경고를 따를 것)
docker --version
```

---

## 2. 최초 셋업 (venv · pip · npm)

작업 디렉터리는 프로젝트 루트 `C:\Users\andul\kospi-watcher` 다. **하위에 `kospi-watcher/` 를 다시 만들지 않는다(이중 중첩 금지).**

### 2.1 Python 백엔드 (단일 venv `.venv`, src-layout 패키지 `kospi_watcher`)

```powershell
# 1) venv 생성 (.venv)
python -m venv .venv

# 2) pip 업그레이드 (3.14 휠 이슈 예방)
.venv\Scripts\python -m pip install --upgrade pip

# 3) 로컬 개발 세트 설치 = core + editable(-e .) + dev 툴체인
#    asyncpg는 포함되지 않는다(= prod 전용). 3.14 휠 문제를 먼저 제거한다.
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

설치 구성(요약):
- `requirements.txt` — 코어 런타임(fastapi, uvicorn, pydantic, sqlalchemy, **aiosqlite**, alembic, httpx, **apscheduler**, redis, **fakeredis**, structlog, pyyaml, tzdata). `asyncpg`는 **없음**.
- `requirements-dev.txt` — `-r requirements.txt` + `-e .`(editable) + pytest/pytest-asyncio/ruff/mypy/types-pyyaml.
- `requirements-prod.txt` — `-r requirements.txt` + **`asyncpg`**(프로드/Docker 전용, 로컬 설치 강제 금지).

editable 설치(`-e .`)가 정상인지 src-layout import 스모크로 확인한다.

```powershell
.venv\Scripts\python -c "import kospi_watcher; print('kospi_watcher OK', kospi_watcher.__file__)"
```

### 2.2 프런트엔드 (npm workspaces, 루트에서 설치)

```powershell
# 루트에서 워크스페이스 전체 설치 (apps/web 포함)
npm install
```

> 참고: `apps/web` 단독으로 설치하려면 `cd apps/web; npm install` 도 가능하다. 운영 표준은 루트 `npm install` 이다.

---

## 3. 환경변수 설정 (.env.example 복사, 주요 변수 의미)

`.env` 는 **절대 커밋하지 않는다**(`.gitignore`에서 `.env`/`.env.*` 제외, `!.env.example`만 허용). 비밀값은 코드/로그/프런트엔드/API 응답에 노출하지 않는다. `.env.example`에는 **변수명만** 있고 값은 비어 있다.

```powershell
# 예시 파일을 복사해 로컬 .env 생성
Copy-Item .env.example .env
```

> 로컬 무도커 모드에서는 `.env` 없이도 동작한다(아래 기본값 참조). 다만 외부 데이터 키(DART/ECOS/NAVER 등)나 Postgres/Redis 전환이 필요할 때만 `.env`를 채운다.

### 주요 변수 의미

| 변수 | 의미 | 로컬 기본/권장 |
| --- | --- | --- |
| `APP_ENV` | 실행 환경 식별 | `development` |
| `APP_NAME` | 앱 이름 | `KOSPI-WATCHER` |
| `DATABASE_URL` | DB 연결 문자열. **미설정/sqlite 계열이면 로컬 SQLite(`aiosqlite`)** 사용 | 비움(= SQLite 기본) |
| `REDIS_URL` | Redis 연결 문자열. **미설정/미가동 시 `fakeredis` 폴백** + 상태 정직 보고 | 비움(= fakeredis) |
| `ANTHROPIC_API_KEY` | 에이전트 LLM 키. 이 Phase는 **mock만**, 실호출 없음 | 비움 |
| `KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NUMBER` | 한국투자증권(실/모의 분리). 이 Phase 미사용 | 비움 |
| `KIWOOM_APP_KEY` / `KIWOOM_APP_SECRET` | 키움증권. 이 Phase 미사용 | 비움 |
| `DART_API_KEY` | DART 공시 | 비움 |
| `ECOS_API_KEY` | 한국은행 ECOS | 비움 |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 뉴스 수집 | 비움 |
| `TRADING_MODE` | 운용 모드 | **`RESEARCH`** (고정) |
| `LIVE_TRADING_ENABLED` | 실거래 토글 | **`false`** (고정) |
| `AUTO_EXECUTION_ENABLED` | 자동집행 토글 | **`false`** (고정) |

> **안전 규칙:** 환경변수 하나만 바꿔 실거래가 켜지는 구조를 만들지 않는다. PAPER와 LIVE 키는 분리하며 절대 공유하지 않는다. 운영 비밀값은 Claude Code/LLM이 읽거나 출력하지 않는다.

---

## 4. DB 마이그레이션 (SQLite 기본, Postgres 전환법)

마이그레이션은 Alembic 단일 체계로, **SQLite·Postgres 양립**(JSONB/네이티브 UUID 회피, `Numeric`/`DateTime(timezone=True)`/`JSON`/`String` 사용)으로 설계되어 있다.

### 4.1 로컬 (SQLite 기본 — `DATABASE_URL` 미설정/sqlite)

```powershell
# 최신 스키마로 업그레이드 (SQLite 기본)
.venv\Scripts\python -m alembic upgrade head

# 되돌리기 (전체 다운그레이드)
.venv\Scripts\python -m alembic downgrade base

# 현재 리비전 / 이력 확인
.venv\Scripts\python -m alembic current
.venv\Scripts\python -m alembic history
```

> 검증 게이트의 일부로 **`upgrade head` → `downgrade base`** 왕복이 깨지지 않아야 한다(reversible 원칙).

### 4.2 Postgres 전환 (프로드/Docker 환경)

Postgres는 `DATABASE_URL` 한 줄로 전환한다. `asyncpg`는 prod 전용이므로 **그 환경에서만** 설치한다.

```powershell
# (해당 환경에서만) prod 의존성 설치 = core + asyncpg
.venv\Scripts\python -m pip install -r requirements-prod.txt

# Postgres를 가리키도록 DATABASE_URL 설정 (예시 — 실제 자격증명은 .env/시크릿)
$env:DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@HOST:5432/kospi_watcher"

# 동일한 마이그레이션 명령 (대상만 Postgres)
.venv\Scripts\python -m alembic upgrade head
```

> 이 장비에는 Postgres가 없으므로 위 전환은 **로컬에서 검증하지 않는다.** Docker/프로드 환경 전용이다.

---

## 5. 로컬 실행 (무도커): 각 서비스 명령 + 웹

무도커 로컬모드에서는 DB=SQLite, 캐시/큐=fakeredis, worker=APScheduler 로 동작한다. 각 백엔드 서비스는 `apps/<svc>/main.py` 를 진입점으로 가지며, FastAPI 앱은 `main:app` 으로 노출된다.

### 5.1 API (port 8000)

```powershell
.venv\Scripts\python -m uvicorn main:app --app-dir apps/api --port 8000
```

### 5.2 worker / agent-service / execution-gateway

각 서비스도 `apps/<svc>/main.py` 진입점을 사용한다.

```powershell
# worker (APScheduler 기반 스케줄러/비동기 처리)
.venv\Scripts\python apps/worker/main.py

# agent-service (mock 에이전트 실행 — 주문 실행 권한 없음)
.venv\Scripts\python apps/agent-service/main.py

# execution-gateway (브로커 격리 — 이 Phase는 실주문 없음, 안전 mock만)
.venv\Scripts\python apps/execution-gateway/main.py
```

> agent-service / execution-gateway 가 FastAPI 앱을 노출한다면 API와 동일한 형태로도 실행할 수 있다(포트는 충돌하지 않게 분리). 예: `.venv\Scripts\python -m uvicorn main:app --app-dir apps/agent-service --port 8100`. 정규 진입점은 위의 `apps/<svc>/main.py` 다.

### 5.3 웹 (Next.js, port 3000)

```powershell
cd apps/web
npm install
npm run dev
```

브라우저에서 http://localhost:3000 접속. 최소 화면: `/`(소개·운용모드·LIVE TRADING DISABLED), `/dashboard`(mock 명시), `/agents`, `/risk`, `/system`.

---

## 6. Docker Compose 실행법 + 이 장비 미검증 경고

`docker-compose.yml` 과 서비스별 `Dockerfile` 은 작성되어 있으며, 최소 서비스 `postgres, redis, api, web, worker, agent-service, execution-gateway` 를 포함한다(healthcheck, 의존성, named volume, 개발 포트, 비밀값 비하드코딩, agent-service↔execution-gateway 책임 분리).

정규 실행 형태(Docker가 설치된 환경 기준):

```powershell
# 빌드 + 기동
docker compose up --build

# 백그라운드 기동 / 상태 / 로그 / 종료
docker compose up -d
docker compose ps
docker compose logs -f api
docker compose down
```

> **⚠️ 이 장비 미검증 경고:** 이 장비에는 **Docker가 설치돼 있지 않다.** 따라서 `docker compose up` 은 **이 장비에서 실행·검증되지 않았다.** compose/Dockerfile은 작성만 된 상태이며, 본 절차는 Docker가 설치된 별도 환경에서만 유효하다. 통과한 것처럼 보고하지 않는다(보고 시 "미검증(Docker 미설치)"로 명시).

---

## 7. 헬스체크 · 상태 확인

API 기동 후(무도커: SQLite + fakeredis) 다음으로 상태를 확인한다. **응답에는 비밀값이 포함되지 않는다.**

```powershell
# 종합 헬스 (API/DB/Redis 상태, trading mode, live trading enabled 여부)
Invoke-RestMethod http://localhost:8000/health

# 시스템 상태 (서비스 버전, 환경, 서버 시각, trading mode, 기능 플래그, 데이터 소스 placeholder)
Invoke-RestMethod http://localhost:8000/api/v1/system/status
```

확인 포인트:
- `trading mode` = `RESEARCH`, `live trading enabled` = `false` 인지.
- DB 상태가 정상(SQLite)인지.
- Redis 상태가 **`fakeredis` 폴백**으로 **정직하게** 보고되는지(실제 Redis 미가동).

빠른 점검용 보조 엔드포인트:

```powershell
# 등록된 mock agent 목록
Invoke-RestMethod http://localhost:8000/api/v1/agents

# 개발용 Audit Log (pagination, 민감정보 제외)
Invoke-RestMethod http://localhost:8000/api/v1/audit-logs
```

---

## 8. 로그 확인

로깅은 **structlog 기반 구조화 JSON 로그**다. 기본적으로 각 서비스 표준출력(stdout)으로 출력된다. PowerShell에서 콘솔 로그를 파일로 함께 남기려면 `Tee-Object`를 사용한다.

```powershell
# API 로그를 콘솔 + 파일로 동시 출력
.venv\Scripts\python -m uvicorn main:app --app-dir apps/api --port 8000 2>&1 | Tee-Object -FilePath .\logs\api.log
```

JSON 로그에서 특정 필드/이벤트만 골라 보려면 PowerShell 파이프라인을 활용한다(콘솔/Bash의 `grep` 대신 `Select-String`).

```powershell
# 파일에서 에러 레벨만 추출
Select-String -Path .\logs\api.log -Pattern '"level":"error"'

# 한 줄씩 JSON으로 파싱해 메시지만 보기 (구조화 로그)
Get-Content .\logs\api.log | ForEach-Object { ($_ | ConvertFrom-Json).event }
```

> **로그 안전:** 비밀값(API 키/계좌번호/토큰/비밀번호)은 로그에 출력하지 않는다. 실거래 관련 설정 변경은 별도 감사(Audit) 로그 대상이다.

---

## 9. 검증 게이트 실행 (전체 명령)

로컬에서 **전부 실제로** 실행한다. `docker compose up` 만 이 장비에서 미검증이다.

### 9.1 백엔드 (Python)

```powershell
# 린트
.venv\Scripts\python -m ruff check .

# 타입 체크
.venv\Scripts\python -m mypy

# 테스트
.venv\Scripts\python -m pytest

# 마이그레이션 왕복 (reversible 확인, SQLite)
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic downgrade base
```

### 9.2 프런트엔드 (web)

```powershell
cd apps/web

# ESLint
npm run lint

# 타입 체크 (tsc --noEmit)
npm run typecheck

# 프로덕션 빌드
npm run build
```

> 루트에서 워크스페이스 스크립트로도 실행 가능: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test` (각각 `apps/web` 위임).

### 9.3 한 번에 (참고 순서)

```powershell
.venv\Scripts\python -m ruff check . ; `
.venv\Scripts\python -m mypy ; `
.venv\Scripts\python -m pytest ; `
.venv\Scripts\python -m alembic upgrade head ; `
.venv\Scripts\python -m alembic downgrade base
# 이어서 web:
cd apps/web ; npm run lint ; npm run typecheck ; npm run build
```

> `;` 는 앞 명령 실패와 무관하게 다음을 진행한다. 게이트를 **엄격히 순차 중단**하려면 PowerShell 7의 `&&` 로 연결한다(앞이 성공해야 다음 실행).

---

## 10. 장애 대응 플레이북

증상 → 원인 → 조치 순서. 무도커 로컬모드 기준.

### 10.1 DB 연결 실패

- **증상:** `/health` 의 DB 상태 비정상, 기동 시 SQLAlchemy 연결 오류.
- **원인 후보:** `DATABASE_URL` 오설정(로컬인데 Postgres를 가리킴), SQLite 파일 권한/경로, 마이그레이션 미적용.
- **조치:**
  ```powershell
  # 1) DATABASE_URL 확인 — 로컬은 비워서 SQLite 기본을 쓴다
  $env:DATABASE_URL
  Remove-Item Env:\DATABASE_URL   # Postgres를 잘못 가리키면 해제 후 재기동

  # 2) 마이그레이션 적용
  .venv\Scripts\python -m alembic upgrade head
  ```
  - 로컬에서 Postgres URL을 쓰면 `asyncpg` 미설치로 실패한다 → 로컬은 SQLite로 두거나, 필요한 환경에서만 `requirements-prod.txt` 설치.

### 10.2 포트 충돌 (8000 / 3000)

- **증상:** `address already in use`, 기동 실패.
- **조치:**
  ```powershell
  # 8000 포트를 점유한 프로세스 확인
  Get-NetTCPConnection -LocalPort 8000 -State Listen |
    Select-Object LocalAddress, LocalPort, OwningProcess
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess

  # 필요 시 종료 (PID 확인 후)
  Stop-Process -Id <PID> -Confirm:$false

  # 또는 다른 포트로 기동
  .venv\Scripts\python -m uvicorn main:app --app-dir apps/api --port 8001
  ```
  - 웹은 `npm run dev -- -p 3001` 로 포트 변경.

### 10.3 마이그레이션 실패

- **증상:** `alembic upgrade head` 또는 `downgrade base` 오류, "Can't locate revision" / 부분 적용.
- **조치:**
  ```powershell
  # 현재 상태/이력 점검
  .venv\Scripts\python -m alembic current
  .venv\Scripts\python -m alembic history

  # 로컬 SQLite는 파일 삭제로 깨끗이 재생성 가능 (.gitignore: *.db / *.sqlite3)
  Get-ChildItem -Filter *.sqlite3 | Remove-Item -Confirm:$false
  Get-ChildItem -Filter *.db | Remove-Item -Confirm:$false
  .venv\Scripts\python -m alembic upgrade head
  ```
  - 다운그레이드가 깨지면 해당 리비전의 `downgrade()` 가 reversible한지 점검(JSONB/네이티브 UUID 사용 여부 등 SQLite·Postgres 양립 위반 확인).

### 10.4 Redis 폴백 (미가동 시 fakeredis)

- **증상/정상동작:** 이 장비에는 Redis가 없으므로 `/health` 의 Redis 상태가 **`fakeredis` 폴백**으로 보고된다. 이는 **오류가 아니라 설계된 폴백**이다.
- **확인/전환:**
  ```powershell
  # REDIS_URL이 비어 있으면 fakeredis 폴백 (정상)
  $env:REDIS_URL

  # 실제 Redis가 있는 환경에서만 설정해 전환
  $env:REDIS_URL = "redis://localhost:6379/0"
  ```
  - 폴백 상태를 실제 Redis 정상으로 위장 보고하지 않는다(정직 보고 원칙).

### 10.5 Python 3.14 휠 이슈

- **증상:** `pip install` 중 C-확장 패키지(대표적으로 `asyncpg`) 휠 부재/빌드 실패.
- **핵심 원칙:** 로컬 세트(`requirements-dev.txt`)에는 `asyncpg`가 **없다.** 로컬에 `asyncpg`를 강제 설치하지 않는다.
- **조치:**
  ```powershell
  # 1) pip/빌드 백엔드 최신화 후 로컬 세트만 설치
  .venv\Scripts\python -m pip install --upgrade pip setuptools wheel
  .venv\Scripts\python -m pip install -r requirements-dev.txt

  # 2) asyncpg는 prod 환경에서만 (로컬에서 실패하면 설치 자체를 하지 않는다)
  #    프로드/Docker: .venv\Scripts\python -m pip install -r requirements-prod.txt
  ```
  - 다른 패키지에서 휠 문제가 나면 해당 패키지의 3.14 호환 버전(하한 핀 이상)을 확인하고, 불가 시 ADR/보고서에 기록한다(추측 임시방편 금지).

---

## 11. DB 백업 · 복구 개요

### 11.1 로컬 (SQLite)

로컬 DB는 단일 파일(`*.sqlite3` / `*.db`, 기본적으로 git 추적 제외)이다. 백업/복구는 파일 복사로 충분하다.

```powershell
# 백업 (타임스탬프 디렉터리)
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force "infra/backup/$ts" | Out-Null
Get-ChildItem -Filter *.sqlite3 | Copy-Item -Destination "infra/backup/$ts/"
Get-ChildItem -Filter *.db      | Copy-Item -Destination "infra/backup/$ts/"

# 복구 (서비스 중지 후 파일 되돌리기)
Copy-Item "infra/backup/<TIMESTAMP>/*.sqlite3" -Destination . -Force
```

> 백업 후 `alembic current` 로 리비전을 확인하고, 복구 후에도 동일 리비전인지 점검한다.

### 11.2 Postgres (프로드/Docker, 이 장비 미적용)

Postgres 환경에서는 논리 백업(`pg_dump`)/복구(`pg_restore` 또는 `psql`)를 사용한다. 이 장비에는 Postgres/Docker가 없어 **미적용·미검증**이다.

```powershell
# (Docker/프로드 환경 예시 — 이 장비에서는 실행하지 않음)
docker compose exec postgres pg_dump -U <USER> -d kospi_watcher -Fc -f /backups/kw.dump
docker compose exec postgres pg_restore -U <USER> -d kospi_watcher --clean /backups/kw.dump
```

> 백업 산출물 디렉터리: `infra/backup/`. 백업 파일에 비밀값이 섞이지 않도록 관리하고, 백업 자체도 접근 통제 대상이다.

---

## 12. Kill Switch 운영 원칙

Kill Switch와 Risk Engine은 **순수 코드(LLM 없음)** 로 구현되며, deny-by-default(명시 승인 없는 주문은 모두 거절)다. 다음 **8가지 트리거** 중 하나라도 발생하면 최종적으로 Kill Switch가 작동해야 한다.

1. 계좌 대사 불일치(reconciliation mismatch)
2. 중복 주문 감지(duplicate order / idempotency key 충돌)
3. 일일 손실 한도 초과
4. 가격 데이터 지연(stale price/quote)
5. 브로커 API 연속 오류
6. 비정상 주문 수량
7. 전략 버전 불일치
8. 운영자의 긴급 중지(operator manual stop)

운영 원칙:
- Kill Switch 발동 시 신규 주문 흐름을 즉시 차단하고 상태를 Audit Log로 남긴다.
- 테스트를 통과시키기 위해 리스크 통제를 약화하지 않는다.
- 리스크 한도(`config/risk_limits.yml` 등) 변경은 ADR 또는 변경 로그로 기록한다.
- 이 Phase에는 **실제 계좌 주문 기능이 없다**(브로커 인터페이스 + 안전 mock만). Kill Switch는 상태 머신/규칙/테스트 수준에서 동작을 보장한다.

---

## 13. PAPER → LIVE 전환 전 체크리스트

실거래는 기본 OFF이며, **명시적 별도 요청 전까지 구현/활성화하지 않는다.** PAPER에서 LIVE로 넘어가기 전, 아래 항목을 **모두** 충족·검증한다(하나라도 미충족 시 전환 금지).

- [ ] 운용 모드 캐논 확인: `TRADING_MODE`, `LIVE_TRADING_ENABLED=false`, `AUTO_EXECUTION_ENABLED=false` 상태에서 시스템이 정상 동작.
- [ ] PAPER와 LIVE **자격증명 분리** 확인(키 공유 없음). 운영용 키와 모의투자 키 분리.
- [ ] 비밀값 비노출: API 응답/로그/프런트엔드/코드에 키·계좌번호·토큰·비밀번호 없음.
- [ ] 모든 주문이 **RiskDecision(APPROVED)** 을 거침. `ApprovedOrder`는 APPROVED RiskDecision 없이는 생성 불가(팩토리 raise).
- [ ] 모든 주문에 **idempotency key** 존재, 동일 키 중복 주문 거부 확인.
- [ ] **Agent Service ↔ Execution Gateway 격리** 확인: agent-service / `domain/agents` 소스에 `submit_order` 임포트 경로 없음(소스/AST 스캔 테스트 통과 — 스펙 테스트 #8).
- [ ] 주문 **상태 머신**(13상태) 정상, 불법 전이 시 예외 발생.
- [ ] 체결/잔고 **대사(reconciliation)** 경로 동작, 대사 불일치 시 Kill Switch 트리거.
- [ ] **Kill Switch 8 트리거** 동작 검증(§12).
- [ ] 데이터 시점 원칙(point-in-time): `available_at` 이후에만 데이터가 전략에 사용, 미래 데이터 유입 없음.
- [ ] mock 데이터가 실데이터로 위장되지 않음("MOCK DATA — NOT REAL MARKET DATA" 배너).
- [ ] 검증 게이트 전부 통과(§9): ruff / mypy / pytest / alembic 왕복 / (web) eslint / tsc --noEmit / next build.
- [ ] 실거래 관련 설정 변경이 **별도 Audit Log** 대상으로 기록됨.
- [ ] 외부 공식 API 명세가 불확실하면 추측 구현하지 않음(미확정 항목은 전환 보류 사유로 기록).
- [ ] (GUARDED_LIVE) 실계좌 주문 전마다 사용자 **명시적 승인** 절차 확인 / (AUTO_LIVE) 사전 승인된 전략·한도 내로 제한.

> 위 체크리스트는 전환 **승인 게이트**다. 운영 환경에서 Claude Code 또는 LLM이 실계좌 주문 권한을 갖지 않는다는 원칙을 유지한다.

---

## 부록 A. 자주 쓰는 명령 요약

```powershell
# 최초 셋업
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements-dev.txt
npm install

# 마이그레이션 (SQLite 기본)
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic downgrade base

# 실행 (무도커)
.venv\Scripts\python -m uvicorn main:app --app-dir apps/api --port 8000
.venv\Scripts\python apps/worker/main.py
.venv\Scripts\python apps/agent-service/main.py
.venv\Scripts\python apps/execution-gateway/main.py
cd apps/web ; npm run dev

# 헬스/상태
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/api/v1/system/status

# 검증 게이트
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy
.venv\Scripts\python -m pytest
cd apps/web ; npm run lint ; npm run typecheck ; npm run build
```

## 부록 B. 참고 문서

- `_KICKOFF.md` — 권위 출처(A 오버레이 + B 스펙, §16.8 RUNBOOK 요구).
- `docs/TRADING_SAFETY.md` — 실거래 안전, 상태 머신, idempotency, 대사, Kill Switch, PAPER/LIVE 분리.
- `docs/ARCHITECTURE.md` — 서비스 책임, LLM/주문 영역 경계, Agent↔Execution 격리.
- `docs/THREAT_MODEL.md` — 키 유출/프롬프트 인젝션/중복 주문/시세 지연 등 위협·대응.
- `docs/adr/` — ADR-001~012(특히 ADR-010 deny-by-default, ADR-011 src-layout, ADR-012 npm workspaces·asyncpg prod-only·fakeredis 폴백).
