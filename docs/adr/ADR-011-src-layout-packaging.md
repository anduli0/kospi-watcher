# ADR-011: 모노레포 src-layout (src/kospi_watcher) 패키징 결정

## Status

Accepted (2026-06-17)

## Context

원본 스펙 §15(프로젝트 디렉터리 구조)는 백엔드 도메인을 `src/domain/`, `src/adapters/`, `src/infrastructure/` 아래에 직접 두는 트리를 제시한다. 이 구조는 `src/`가 곧 import 루트인 형태로, 다음 문제가 있다.

- `src/domain`, `src/adapters` 같은 일반명(generic name) 최상위 패키지는 다른 라이브러리와 이름이 충돌하기 쉽고, 무엇이 "이 프로젝트의" 패키지인지 모호하다.
- 단일 배포 가능한 파이썬 패키지로 묶이지 않으면 `pip install -e .`(editable) 설치·배포·버전 관리가 어색하다.
- 다섯 서비스(api, agent-service, execution-gateway, worker, web)가 동일 도메인 코드를 공유해야 하는데, 서비스별로 코드를 복제하면 단일 사실 출처(single source of truth)가 깨진다.

오버레이 D항은 백엔드를 "단일 venv + **src-layout 패키지 `kospi_watcher`** (`src/kospi_watcher/{domain,adapters,infrastructure}`)"로 두고, `pyproject.toml` + `requirements.txt`/`requirements-dev.txt`로 관리하며 `pip install -e .`로 editable 설치한다고 명시한다. 또한 "디렉터리 트리 조정(src 하위 패키지명 도입)은 ADR-011에 기록"하라고 지시한다. 스펙 §15도 "기술적 필요에 따라 일부를 조정할 수 있지만, 변경 이유를 설명하고 ADR에 남긴다"고 허용한다.

## Decision

스펙의 `src/domain`·`src/adapters`·`src/infrastructure`를 **단일 import 패키지 `kospi_watcher` 하위로 이동**하여 **src-layout**으로 패키징하고, `apps/<svc>`는 **얇은 진입점(thin entrypoint)** 으로 둔다.

1. **단일 패키지 src-layout.** 백엔드 도메인을 `src/kospi_watcher/`로 모으고, 그 아래에 `domain/`, `adapters/`, `infrastructure/`를 둔다. 즉 스펙의 `src/domain/...`은 `src/kospi_watcher/domain/...`으로 매핑된다. import 경로는 `kospi_watcher.domain.*`, `kospi_watcher.adapters.*`, `kospi_watcher.infrastructure.*`가 된다.
2. **얇은 진입점.** `apps/api`, `apps/agent-service`, `apps/execution-gateway`, `apps/worker`는 자체 비즈니스 로직을 갖지 않고, `kospi_watcher` 패키지를 import해 조립·기동하는 얇은 진입점 + 각 서비스의 Docker 컨텍스트 역할만 한다. `apps/web`은 Next.js 프런트엔드다.
3. **editable 설치.** `pyproject.toml`에 패키지·도구 설정(ruff/mypy/pytest)을 두고, `pip install -e .`로 단일 venv에 editable 설치한다. 모든 서비스·테스트가 동일 설치본을 공유한다.
4. **경계 강제와의 정합.** `submit_order` 구현은 `kospi_watcher.domain.execution.broker`와 `apps/execution-gateway`에만 두고, `apps/agent-service`/`kospi_watcher.domain.agents`에는 import 경로가 없게 한다(ADR-001/002). src-layout의 명시적 패키지 경로 덕에 AST/문자열 스캔 테스트(스펙 테스트 #8)가 정확해진다.
5. **Step 0 디리스크.** venv 생성 + 로컬 세트 설치(asyncpg 제외) 후, src-layout import 스모크 pytest로 패키지 임포트 가능성을 먼저 검증한다(ADR-012 연계).

## Consequences

- 모든 서비스가 `kospi_watcher` 단일 패키지를 공유해, 도메인 로직의 단일 사실 출처가 보장되고 코드 복제가 사라진다.
- src-layout은 "설치된 패키지"를 테스트·실행하게 강제하므로, 우연히 현재 작업 디렉터리에서 import되는 문제(테스트가 미설치 코드를 잡는 류의 버그)를 예방한다.
- 일반명(`domain`, `adapters`) 최상위 패키지 충돌이 사라지고, import 경로가 `kospi_watcher.*`로 명확해진다.
- `apps/<svc>`가 얇아져, 서비스별 Docker 컨텍스트/진입점과 공유 도메인 코드의 책임이 분리된다. 서비스 추가가 진입점 추가로 끝난다.
- 스펙의 원래 트리(`src/domain/...`)와 1:1로 다르므로, 문서·예시 경로를 `src/kospi_watcher/...`로 일관되게 갱신해야 한다. 이 ADR이 그 매핑의 근거다.
- editable 설치·src-layout에 익숙하지 않은 기여자는 `pip install -e .` 선행이 필요함을 인지해야 한다(RUNBOOK 연계).

## Alternatives Considered

- **스펙 원안 그대로 `src/domain`·`src/adapters` 최상위(rejected).** 변경이 없어 단순하나, 일반명 패키지 충돌·editable 설치 어색함·단일 패키지화 부재 문제가 남는다. 오버레이 D가 `kospi_watcher` 패키지를 명시하므로 기각.
- **flat-layout(`kospi_watcher/`를 리포 루트에 직접)(considered, not chosen).** `src/` 없이 패키지를 루트에 둠. 더 단순하나, 작업 디렉터리에서 우발적으로 import되어 "미설치 코드"를 테스트가 잡는 고전적 함정이 생긴다. src-layout이 이를 구조적으로 예방하므로 채택하지 않았다.
- **서비스별 개별 패키지 + 내부 의존(considered, not chosen).** 각 app을 독립 파이썬 패키지로 쪼개고 공유 코드를 별도 패키지로. 대규모 조직엔 유효하나, 이번 규모에선 버전 핀·상호 의존 관리 비용이 과하고 단일 venv 단순성을 해친다. 단일 `kospi_watcher` 패키지 + 얇은 app 진입점으로 시작한다.
