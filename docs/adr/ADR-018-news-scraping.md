# ADR-018: 키리스 Google News RSS 뉴스 스크랩 + defusedxml 파싱 + 일자별·보존 정리(retention) 저장 + 뉴스 인지 데일리 브리핑

## Status

Accepted (2026-06-17)

## Context

제품의 무게중심이 **시장 예측 + 데일리 브리핑**으로 이동하면서(ADR-016·ADR-017), 브리핑이 "왜 이 방향인가"를 설명할 때 **최근 뉴스 흐름**을 함께 제시할 필요가 생겼다. 그동안 시스템은 시세는 키리스 Yahoo로 가져왔지만(ADR-013) 뉴스에 대한 수집·저장 경로가 없었다. 요구사항: (a) 뉴스 수집은 **API 키 없이**, 그리고 형제 시스템과 같은 로컬·무도커 환경(ADR-012)에서 동작해야 한다. (b) 외부 XML을 파싱하므로 **XML 공격(엔티티 폭발 등)에 안전**해야 한다. (c) 제공자는 시세 provider와 같은 계약 — **절대 예외를 던지지 않고** 실패 시 빈 결과를 반환해 스크랩이 안전하게 열화 — 을 따라야 한다(원칙: "추측 금지·안전 우선", PRODUCT_SPEC §1.3). (d) 뉴스는 **일자별로** 조회 가능해야 하고, 무한정 쌓이면 안 되므로 **보존 기간(retention)**을 넘긴 항목은 정리되어야 한다. (e) mock은 mock으로 — 오프라인/테스트용 가짜 뉴스는 실데이터로 오인되면 안 된다(`MOCK` 라벨). (f) 수집된 뉴스가 **데일리 브리핑의 근거**로 쓰이되, 결정론적 예측 종합(ADR-017)의 수치를 바꾸지 않아야 한다 — 뉴스는 서사·참고용이고, 어떤 에이전트에도 주문 권한을 주지 않는다(ADR-001).

## Decision

`infrastructure/news/`에 키리스 뉴스 provider 추상화를 도입하고, `newsfeed/service.py`의 `NewsService`가 이를 일자별·보존 정리되는 `news_items` 테이블에 저장하며, 그 헤드라인을 데일리 브리핑 종합에 전달한다.

1. **Provider 추상화(`infrastructure/news/base.py`).** `NewsItem`(`id`, `title`, `url`, `source`, `topic`, `published_at`(`AwareDatetime`), `summary`; `extra="forbid"`) 모델, `make_item_id(url, title)`(canonical URL 기반 `sha256` 16진 32자, URL 없으면 title 폴백 — dedup 키), `NewsProvider` `Protocol`을 정의한다. 계약상 provider의 `fetch`는 **절대 예외를 던지지 않고** 실패 시 `[]`를 반환한다(시세 provider, ADR-013과 동일 철학).

2. **키리스 Google News RSS(`google_rss.py`, `GoogleNewsProvider`, `name="google"`).** 공개 Google News RSS 검색 엔드포인트(`https://news.google.com/rss/search`, 파라미터 `q=<topic>&hl=ko&gl=KR&ceid=KR:ko`)에서 **API 키 없이** 한국어 결과를 가져온다(브라우저 `User-Agent` 전송). XML은 **`defusedxml`**(`defusedxml.ElementTree.fromstring`)로 파싱해 엔티티 폭발 등 XML 공격에 안전하다. `httpx.HTTPError`/`ParseError`/`ValueError`/`DefusedXmlException` 또는 비-200 응답이면 `[]`를 반환해 **절대 예외를 던지지 않는다**. 항목별로 제목의 후행 `" - <source>"` 접미사를 제거하고, `make_item_id`로 id를 만들며, `pubDate`(RFC-2822)를 파싱한다(없거나 파싱 실패 시 `now_utc()`, naive면 UTC 부여). `httpx.AsyncClient`는 주입 가능해 오프라인 테스트가 가능하고, 자기 소유 클라이언트는 `aclose()`로 정리한다.

3. **오프라인 mock(`mock.py`, `MockNewsProvider`, `name="mock"`).** 결정론적이고 `[MOCK]` 라벨이 붙은 헤드라인만 반환하며 네트워크에 접근하지 않는다.

4. **Factory(`factory.py`).** `get_news_provider()`가 `news_provider` 설정(`"google"` 기본, 아니면 `"mock"`)으로 백엔드를 고르고 프로세스 전역 싱글턴을 캐시한다. `reset_news_provider()`가 이를 폐기(Google 클라이언트 close 포함)한다.

5. **스크랩·dedup·보존(`newsfeed/service.py`, `NewsService.scrape`).** 설정된 `news_topics` 각각에 대해 `provider.fetch`를 호출하고, **토픽 간 중복을 item id로 제거**한 뒤, 새 항목만 **upsert**(`repositories.upsert_news` — 이미 저장된 id는 건너뜀)하고, **`news_retention_days`(기본 14일)**보다 오래된 항목(`published_at < now − retention`)을 **prune**(`repositories.prune_news`)한 다음 커밋한다. `ScrapeResult(fetched, added, pruned, topics)`를 반환한다. 보존 정리는 매 스크랩마다 강제되어 피드가 스테일 히스토리를 쌓지 않는다.

6. **저장·일자 그룹핑(`db/models.py` `NewsItemRow`, Alembic `0004_news.py`, `0003`→`0004`).** `news_items`는 `id`(PK, dedup 대상), `title`/`url`(`Text`), `source`/`topic`, `published_at`(tz-aware, 인덱스), **`date_kst`**(KST 캘린더 일자 문자열, 인덱스 — upsert 시 `to_kst(published_at).date()`로 산출), `summary`, `created_at`을 가진다. `topic`·`published_at`·`date_kst`에 인덱스를 둔다. 리포지토리: `upsert_news`, `prune_news`, `list_news(date_kst?, limit)`, `news_dates`(일자→건수), `recent_headlines(limit=8)`.

7. **엔드포인트·워커(`api/routes/news.py`, `/api/v1`).** `GET /news`(최근 항목, 선택적 `?date=YYYY-MM-DD`·`limit`), `GET /news/dates`(KST 일자별 건수), `POST /news/scrape`(즉시 스크랩→`ScrapeResult` 카운트). 워커 `scrape_news` 잡이 **60분마다** 동일 경로를 수행한다(`worker/scheduler.py`).

8. **뉴스 인지 데일리 브리핑.** `PredictionService.generate`가 `news_headlines=`를 받아 종합기(`synthesize(..., news_headlines=...)`)에 넘긴다. `POST /prediction/run` 라우트와 워커 `refresh_prediction` 잡 모두 `repositories.recent_headlines`로 이를 채운다. 종합기는 비어 있지 않은 헤드라인 최대 5건을 `MarketPrediction.news_refs`로 보존하고 상위 1건을 한국어 브리프 서사에 엮는다("최근 '<headline>' 등 뉴스 흐름도 함께 반영했다"). 뉴스는 **서사·참고용**이며 **결정론적 데스크/수석 종합 수치를 바꾸지 않는다**(예측은 여전히 finding의 순수 함수).

9. **설정·의존성.** `config.py`: `news_provider`(`"google"|"mock"`, 기본 `"google"`), `news_retention_days`(기본 14), `news_topics`(기본 한국어 토픽). 신규 의존성 **`defusedxml>=0.7`**(`pyproject.toml`·`requirements.txt`).

## Consequences

- 데일리 브리핑이 **최근 뉴스 흐름을 근거**로 함께 제시되어 설명력이 커진다. `news_refs`로 어떤 뉴스를 반영했는지 투명하게 드러난다.
- 뉴스 수집이 **키 없이** 동작해 로컬·무도커 환경(ADR-012)과 형제 시스템 운영 방식에 부합한다. 키 관리 부담이 없다.
- 외부 XML을 **`defusedxml`**로 파싱하고 provider가 **절대 예외를 던지지 않으므로**, 악의적/깨진 피드나 네트워크 장애가 스크랩·예측 경로를 무너뜨리지 못한다(안전 열화).
- `news_items`가 **일자별·보존 정리** 구조라 `뉴스` 화면이 일자별로 묶여 조회되고, `news_retention_days`로 저장량이 한정된다. 테이블이 11개가 된다(ARCHITECTURE §5, Alembic 4개 마이그레이션).
- **무권한 불변식 유지.** 뉴스는 브리프의 서사·참고용일 뿐 결정론 종합 수치를 바꾸지 않고, 어떤 에이전트·예측도 주문 권한을 얻지 않는다(ADR-001, ADR-017). mock 뉴스는 `[MOCK]`으로 라벨되어 실데이터로 오인되지 않는다.
- `news_retention_days`(14)·토픽·스크랩 주기(60분)는 **현재의 합리적 기본값**이며 설정으로 조정 가능하다.

## Alternatives Considered

- **유료/키 기반 뉴스 API(NewsAPI 등) 사용(rejected).** 더 풍부할 수 있으나 API 키 관리가 필요하고 로컬·무도커 철학(ADR-012)과 어긋나며 비용·레이트리밋이 따른다. 키리스 Google News RSS로 충분한 헤드라인을 얻는다.
- **표준 `xml.etree.ElementTree`로 파싱(rejected).** 외부에서 받은 XML을 표준 파서로 처리하면 엔티티 폭발 등 공격에 노출된다. `defusedxml`로 안전하게 파싱한다(보안 의존성 1개 추가가 합리적 트레이드오프).
- **뉴스를 저장하지 않고 매 요청 실시간 호출(considered, not chosen).** 단순하지만 매 조회가 외부 호출을 유발해 느리고 레이트리밋 위험이 있으며, 일자별 그룹핑·보존을 제공하기 어렵다. `news_items`에 저장하고 워커가 60분마다 갱신해 조회는 저장본을 읽는다.
- **보존 정리 없이 무한 적재(rejected).** 구현은 쉽지만 피드가 스테일 히스토리로 무한정 커진다. 매 스크랩마다 `news_retention_days`를 넘긴 항목을 prune한다.
- **뉴스를 에이전트 입력으로 주입해 finding을 바꿈(rejected).** 뉴스를 종합 수치에 반영하면 예측의 결정론·재현성(ADR-017)이 흔들리고, "분석은 가변, 종합은 불변" 경계가 깨진다. 뉴스는 브리프 서사·참고용으로만 두고 수치는 finding의 순수 함수로 유지한다.
- **provider가 실패 시 예외를 던지게 함(rejected).** 호출부마다 방어 코드가 필요하고 한 토픽의 장애가 전체 스크랩을 깨뜨린다. 시세 provider(ADR-013)와 동일하게 `fetch`는 절대 예외를 던지지 않고 `[]`를 반환한다.
