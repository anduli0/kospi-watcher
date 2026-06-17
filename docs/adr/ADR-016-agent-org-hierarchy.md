# ADR-016: 계층형 리서치 데스크 조직 — 평평한 21-에이전트 목록 대신 5데스크+Chief·3티어·가중·리드 기반 오케스트레이션

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER의 분석 계층은 21개 에이전트가 단일 버전드 `AgentFinding`을 산출하는 고정 카탈로그다(AGENT_DESIGN, ADR-015). 본래 이 21개는 **평평한 목록**으로만 존재했고, 레지스트리는 단순히 이름순으로 `run_all`을 돌려 finding을 모았다(`registry.py`). 이제 제품의 무게중심이 **시장 예측 + 데일리 브리핑**으로 이동하면서(ADR-017), 21개 finding을 하나의 하우스 뷰로 **종합(synthesize)**할 합리적 구조가 필요해졌다.

평평한 목록을 그대로 종합하면 다음 문제가 있다. (a) **균등 취급의 비합리성** — 데이터 무결성 점검 에이전트와 핵심 수급 에이전트가 같은 무게로 방향성에 기여하는 것은 부적절하다. 시장 방향성에 대한 기여도는 영역마다 다르다. (b) **실행 순서의 부재** — 데이터 품질 검증은 방향성 분석보다 **먼저** 수행되어 종합의 신뢰도(또는 `DATA_UNCERTAIN` 강등)를 결정해야 하는데, 평평한 목록에는 티어 개념이 없다. (c) **종합의 구조적 근거 부재** — "왜 이 방향인가"를 설명하려면 어떤 영역(데스크)이 주도했는지, 그 영역 내 누가 리드였는지가 드러나야 하는데, 21개를 평면 평균하면 서사가 만들어지지 않는다(브리핑은 분절 캡션이 아니라 한 이야기여야 한다). (d) **확장·가독성** — 21개 개별 에이전트를 사람이 한눈에 파악하기 어렵다. 6개 데스크로 묶으면 조직도가 읽힌다.

요구사항: (1) 21개 에이전트를 **소수의 데스크**로 묶되, 각 데스크에 **리드**와 **방향성 가중치**를 부여한다. (2) **티어**로 실행/정보 흐름 순서를 명시한다(검증 → 분석 → 종합). (3) 이 구조는 **순수 메타데이터**여야 한다 — 카탈로그(이름·버전·카테고리, ADR-015)를 바꾸지 않고, 아무것도 실행하지 않으며, 종합 로직은 별도 모듈에 둔다. (4) 데스크 멤버십은 카탈로그와 **정확히 일치**해야 하며(드리프트 방지), 21개를 빠짐없이 덮어야 한다. (5) 조직도는 **읽기 전용 API**로 노출 가능해야 한다.

## Decision

21개 에이전트를 **5개 데스크 + 1명의 Chief**로 구성된 계층 조직(`AGENT_ORG`)으로 모델링하되, 이를 `catalog.py` 위의 **순수 메타데이터**(`domain/agents/org.py`)로 둔다. 오케스트레이션은 실행하지 않으며 `domain/prediction/synthesizer.py`(ADR-017)에 위치한다.

1. **데스크·티어·가중치 모델.** `Desk`(StrEnum: `DATA_INTEGRITY`/`MACRO`/`FLOW_TECH`/`FUNDAMENTAL`/`RISK`/`CHIEF`), `Tier`(StrEnum: `VALIDATE`/`ANALYZE`/`SYNTHESIZE` — 낮은 티어가 먼저 실행·정보 제공), `DeskSpec(key, title_ko, tier, weight, lead, members)`을 정의한다. `weight`는 Chief 종합 시 데스크 방향성 기여 가중치이며, 분석 데스크 합이 ~1.0이다.

2. **데스크 로스터(`AGENT_ORG`).** 6개 데스크:
   - `DATA_INTEGRITY` — 데이터·검증 데스크, `VALIDATE`, weight 0.10, lead *Market Data Integrity Agent*, 멤버 3(Market Data Integrity / News Deduplication / Source Verification).
   - `MACRO` — 거시·국제 데스크, `ANALYZE`, weight 0.24, lead *Korea Macro Agent*, 멤버 6(Korea Macro / Global Growth / Rates and Liquidity / FX / Commodity and Energy / Geopolitics and Trade).
   - `FLOW_TECH` — 수급·기술 데스크, `ANALYZE`, weight 0.26, lead *Foreign and Institutional Flow Agent*, 멤버 4(Foreign and Institutional Flow / Derivatives and Program / Breadth and Technical / Volatility and Regime).
   - `FUNDAMENTAL` — 실적·섹터 데스크, `ANALYZE`, weight 0.24, lead *Earnings and Valuation Agent*, 멤버 5(Earnings and Valuation / Technology and Semiconductor / Industrial and Export / Domestic Demand and Defensive / Structural Growth Scout).
   - `RISK` — 리스크·레드팀 데스크, `ANALYZE`, weight 0.16, lead *Red-Team and Risk Agent*, 멤버 2(Red-Team and Risk / Disclosure and Corporate Event).
   - `CHIEF` — 수석 신디사이저, `SYNTHESIZE`, weight 0.00, lead *Chief Market Synthesizer*, 멤버 1.

   방향성 가중치는 분석 데스크에만 의미가 있고, `DATA_INTEGRITY`는 데이터 품질을 게이트하며 작은 방향성 가중치(0.10)를 가지며, `CHIEF`는 종합기(weight 0)다.

3. **순수 메타데이터 + 불변식 강제.** `org.py`는 아무것도 실행하지 않는다(오케스트레이션은 synthesizer). 모듈 로드 시 두 assertion으로 드리프트를 막는다: 데스크 멤버 집합이 `AGENT_CATALOG` 이름 집합과 **정확히 일치**(`set(_DESK_BY_AGENT) == catalog names`)하고, 멤버 수 합이 **21**(`3+6+4+5+2+1`)이다. 멤버 이름은 카탈로그와 글자 그대로 일치해야 한다.

4. **파생 뷰·헬퍼.** `ANALYSIS_DESKS`(`CHIEF` 제외), `DIRECTIONAL_DESKS`(`ANALYZE` 티어 4개), `desk_of(name)`, `desk_spec(key)`, `is_lead(name)`을 제공한다.

5. **티어드 종합과 리드 가중(synthesizer에서 소비).** 종합은 결정론적이다: 데스크 내부는 멤버 finding의 `sign(direction) × (impact_weight × lead_bonus) × confidence`를 가중 평균(`impact` LOW 1 / MEDIUM 2 / HIGH 3, **리드 ×1.5**)하여 데스크 `score`·`lean`·`conviction`을 만들고, Chief는 `overall_score = Σ(desk.weight × desk.score)`로 하우스 방향성·확신도를 만든다. 즉 **데스크 내부는 임팩트×확신·리드 가중, 데스크 간은 데스크 가중치 가중**이다.

6. **읽기 전용 노출.** `GET /api/v1/agents/org`(`api/routes/prediction.py`)가 조직도를 `OrgResponse`(데스크별 key/title/tier/weight/lead/members, 3개 티어 이름, agent_count)로 반환한다.

## Consequences

- 21개 finding이 **합리적·가중·티어드** 구조로 종합된다 — 영역별 기여도(데스크 가중치)와 영역 내 권위(리드 가중)가 명시되어, 평면 평균보다 시장 방향성 추정이 합리적이다. 데이터 검증이 `VALIDATE` 티어로 선행하여 신뢰할 수 없는 입력은 `DATA_UNCERTAIN`으로 강등된다(ADR-017).
- 조직도가 **읽힌다.** 6개 데스크 + Chief, 3개 티어로 21개를 묶으니 사람이 한눈에 파악하고, `/agents/org`로 노출되며, 데일리 브리핑이 "어느 데스크가 주도했는가"라는 **서사**를 가질 수 있다(분절 캡션 회피).
- **카탈로그 계약은 불변.** `org.py`는 순수 메타데이터라 에이전트 이름·버전·카테고리(ADR-015)나 `AgentFinding` 스키마를 바꾸지 않는다. 두 assertion이 카탈로그↔조직 드리프트를 로드 타임에 잡는다(에이전트 추가·이름 변경 시 즉시 실패).
- 가중치·리드·티어는 **현재의 합리적 기본값**이다. 시장 구조 변화에 따라 재조정될 수 있으나, 종합이 결정론적이므로 가중치 변경의 효과는 재현·검증 가능하다.
- **무권한 불변식 유지.** 조직화는 분석 계층 내부의 구조일 뿐, 어떤 데스크·리드·Chief도 주문 권한을 얻지 않는다(ADR-001). Chief Market Synthesizer는 여전히 분석만 하며, 주문 게이트는 deterministic Risk Engine뿐이다.

## Alternatives Considered

- **평평한 21-에이전트 목록 유지(rejected).** 단순하지만 종합 시 모든 에이전트를 균등 취급해 방향성 추정이 비합리적이고, 실행 티어가 없어 데이터 검증을 선행시킬 수 없으며, 브리핑에 "주도 영역" 서사를 만들 수 없다. 데스크 조직으로 합리성·가독성·서사를 얻는다.
- **개별 에이전트별 가중치(considered, not chosen).** 21개 각각에 가중치를 부여하면 세밀하지만 튜닝 표면이 21차원으로 폭증하고 사람이 관리·설명하기 어렵다. 6개 데스크 가중치 + 리드 보너스로 차원을 줄이면서 영역별 기여도를 표현한다.
- **LLM에게 종합을 맡김(rejected).** Chief를 실제 LLM으로 두어 21개 finding을 자유롭게 종합시키는 안은, 결과가 비결정적·비재현이고 감사·백테스트가 어렵다. 종합은 결정론 코드(synthesizer)로 두고, 데스크 조직은 그 코드가 소비하는 메타데이터로 둔다(ADR-017).
- **조직도를 synthesizer 안에 인라인(rejected).** 데스크·가중치를 종합 코드에 하드코딩하면 재사용·노출(`/agents/org`)·테스트가 어렵다. 순수 메타데이터(`org.py`)와 오케스트레이션(`synthesizer.py`)을 분리해 도메인 의존 규칙(inward)을 지킨다.
- **카탈로그를 직접 데스크로 재구조화(rejected).** `catalog.py`에 데스크 필드를 넣으면 ADR-015의 안정적 카탈로그 계약(이름·버전·카테고리)이 흔들리고 스키마 버전과 얽힌다. 조직은 카탈로그 위의 별도 레이어로 두고 assertion으로 일치를 강제한다.
