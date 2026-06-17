# ADR-020: 뉴스 데일리 브리프(뉴스 라운드업)를 예측 리포트와 분리

## Status

Accepted (2026-06-17)

## Context

제품의 1차 산출물은 **예측 리포트**(`MarketPrediction`, ADR-017)다 — 데스크 토의·수석 조율을 거친 결정론적 *예보*(regime·direction/confidence·롱/인버스/곱버스 스탠스·시나리오·한국어 브리프). 그러나 이용자가 매일 아침 가장 먼저 확인하고 싶어 하는 것은 "예보" 외에 **오늘 무슨 뉴스가 있었나"라는 *요약*이기도 하다(자매 시스템 Fed-Watcher/KRW-Watcher의 데일리 브리프와 동일한 무게중심).

ADR-018로 키리스 Google News RSS 스크랩이 도입돼 그날의 헤드라인이 `news_items` 테이블에 일자별(KST `date_kst`)로 적재된다. 이 적재분을 사람이 읽을 한 편의 요약으로 묶는 산출물이 필요했다. 핵심 설계 질문은 두 가지였다: (1) 이 요약을 예측 리포트에 합칠 것인가, 별도 아티팩트로 둘 것인가; (2) 요약 생성을 LLM에 맡길 것인가, 결정론적으로 구성할 것인가.

예측 리포트와 뉴스 요약은 **성격이 다른 두 아티팩트**다. 예측 리포트는 *예보*(앞으로 어떻게 될 것 같은가)이고, 뉴스 데일리 브리프는 *요약*(오늘 무엇이 보도됐는가)이다. 둘을 한 객체에 묶으면 스키마가 비대해지고, "예측인가 요약인가"라는 책임 경계가 흐려지며, 각자의 갱신 주기·보존 정책·표현 방식을 독립적으로 진화시키기 어렵다.

## Decision

**뉴스 데일리 브리프를 예측 리포트와 분리된 별도의 "뉴스 라운드업" 아티팩트로 도입**하고, 결정론적 빌더로 구성하며, KST 일자별 단일 행으로 upsert 저장한다.

1. **별도 스키마(`NewsBrief`).** `domain/news_brief.py`에 `NewsBrief`/`NewsTheme`/`NewsHeadline`을 정의한다(`NEWS_BRIEF_SCHEMA_VERSION = "1.0.0"`, 모두 `extra="forbid"`). `NewsBrief`는 `date`(KST `YYYY-MM-DD`)·`item_count`·`summary`(라운드업 내러티브)·`market_read`(뉴스↔하우스뷰 한 줄 연결)·`themes`(토픽별 묶음)·`generated_by`(`"rule"` 결정론 / `"llm"`)·`created_at`을 담는다. 이는 `MarketPrediction`과 **별개의 타입**으로, 예측 리포트(예보)와 뉴스 브리프(요약)가 서로 다른 아티팩트임을 타입 수준에서 못박는다.
2. **결정론적 빌더(`build_news_brief`).** `newsfeed/brief_builder.py`의 `build_news_brief(date_kst, rows, prediction, *, generated_by="rule")`는 그날의 스크랩 헤드라인(`NewsItemRow`)을 **토픽별로 그룹핑**(테마 내 최신순, 테마는 건수 내림차순)하고, 테마당 최대 4건을 골라 **한 편의 단일 내러티브 요약**과 **한 줄 `market_read`**를 구성한다. 분절된 캡션 묶음이 아니라 하나의 이야기로 엮는다. LLM 호출이 없어 같은 입력에 대해 **재현 가능**하다(기본 `generated_by="rule"`).
3. **market_read 타이인.** `market_read`는 그날의 뉴스를 **최신 예측의 regime/direction**과 한 줄로 잇는다(`_market_read`가 `repositories.get_latest_prediction` → `MarketPrediction`을 받아 "에이전트 21인의 데스크 토의·수석 조율 결과, 시장은 <REGIME_KO> 국면(<방향>, 확신 NN%)으로 읽힌다 — <headline>" 형태로 작성). 예측이 아직 없으면 "아직 오늘의 예측 리포트가 생성되지 않았다"로 정직히 표기한다. 즉 브리프는 예보를 **참조**하되 예보를 **대체하지 않는다**.
4. **일자별 단일 행 upsert + 전용 테이블.** 브리프는 `daily_briefs` 테이블(`DailyBriefRow`, PK = `date_kst` `String(10)`)에 **KST 하루 한 행**으로 저장한다. `repositories.save_daily_brief`가 `date_kst`로 upsert(있으면 갱신, 없으면 삽입)하므로 하루 여러 번 재생성해도 행이 누적되지 않는다. 스칼라 컬럼(`summary`/`market_read`/`item_count`/`generated_by`/`created_at`)은 최신 조회용 인덱스이고, 전체 `NewsBrief`는 `payload`(`JSON`)에 보관한다. 마이그레이션 `alembic/versions/0005_daily_briefs.py`(revision `0005`, down-revision `0004`)가 테이블과 `ix_daily_briefs_created_at` 인덱스를 만든다.
5. **서비스 + API.** `NewsService.generate_daily_brief`(`newsfeed/service.py`)가 그날의 `list_news` 행과 최신 예측을 모아 `build_news_brief`를 호출하고 `save_daily_brief`로 영속화한다. API(`api/routes/news.py`, `/api/v1` 하위)는 `GET /news/brief`(최신 브리프, 없으면 404)와 `POST /news/brief/run`(지금 생성)을 노출한다. 둘 다 `NewsBrief`를 응답한다.

## Consequences

- 예측 리포트(`/prediction`, 예보)와 뉴스 데일리 브리프(`/news/brief`, 요약)가 **명확히 분리된 두 아티팩트**로 존재해, 각자의 스키마·저장소·갱신 경로를 독립적으로 가진다. "이건 예보인가 요약인가"라는 혼동이 사라진다.
- 결정론적 빌더라 LLM 키 없이도 동작하고 같은 입력에 같은 브리프가 나와 테스트·재현이 쉽다. 다만 표현의 다양성은 LLM 생성보다 제한적이다(향후 `generated_by="llm"` 경로로 확장 여지를 남겼다).
- KST 일자별 upsert로 "하루 한 브리프"가 보장돼 행 누적이 없고 "오늘의 브리프" 조회가 단순하다. 반면 같은 날 여러 시점의 스냅샷 이력은 남기지 않는다(설계상 최신본만 의미 있음).
- `market_read`가 최신 예측에 의존하므로, 예측이 아직 없으면 브리프는 그 사실을 정직히 표기한다(예보를 지어내지 않는다). 브리프는 예보를 참조만 하며 예측 산출물의 진실 원천을 침범하지 않는다.

## Alternatives Considered

- **예측 리포트에 뉴스 요약을 합치기(rejected).** `MarketPrediction`은 이미 `news_refs`로 최근 헤드라인을 *참조*한다(ADR-018). 그러나 요약 본문까지 예측에 넣으면 예보용 스키마가 비대해지고 예보/요약 책임이 섞인다. 둘은 성격이 다른 아티팩트이므로 별도 타입·테이블·엔드포인트로 분리한다.
- **LLM으로 요약 생성(considered, not chosen).** 표현은 풍부하나 키·비용·비결정성을 끌어들이고 키리스 로컬모드(ADR-012)와 어긋난다. 결정론적 빌더로 시작하고, `generated_by` 필드로 LLM 경로 확장 여지만 남긴다.
- **일자별 다중 스냅샷 이력 저장(considered, not chosen).** 같은 날의 여러 생성본을 모두 남기면 감사에는 유리하나 "오늘의 브리프"가 모호해지고 행이 누적된다. KST 일자 PK + upsert로 하루 한 행만 유지한다(예측은 `market_predictions`에 누적 저장되므로 이력은 그쪽이 담당).
