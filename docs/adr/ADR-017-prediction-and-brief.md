# ADR-017: 결정론적 예측 종합기 + 단일 서사 데일리 브리핑 + 롱/숏 상품 스탠스(인버스/곱버스), 영속화·워커 갱신

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER의 제품 무게중심을 형제 시스템(Fed-Watcher, KRW-Watcher)과 같이 **시장 예측 + 데일리 브리핑**으로 이동시킨다. 그동안 분석 계층은 21개 `AgentFinding`을 산출했지만(ADR-015), 이를 하나의 **하우스 뷰**로 종합해 사용자에게 "오늘 시장이 어떤 국면이고, 방향은 어디며, 무엇을 어떻게 포지셔닝할지"를 한 화면·한 이야기로 제시하는 산출물이 없었다. ADR-016이 종합의 구조(5데스크+Chief·티어·가중)를 제공했고, 이제 그 위에서 실제 **예측을 합성**하고 **영속화·갱신·노출**하는 결정이 필요하다.

요구사항: (a) 종합은 **결정론적**이어야 한다 — finding이 mock 런타임에서 왔든 실제 LLM 런타임에서 왔든(ADR-015), **같은 finding 집합이면 같은 예측**이 나와 재현·테스트·감사가 가능해야 한다(자금 결정 영역의 "분석은 가변, 종합은 불변" 경계를 예측에도 적용). (b) 결과는 **시장 국면(9종, PRODUCT_SPEC §6.2)**, **방향성·확신도**, **시나리오**를 포함해야 한다. (c) 가장 중요한 제품 요구: **약세 뷰가 실행 가능**해야 한다 — 단순 "롱 회피"가 아니라 **인버스/곱버스(레버리지 인버스) 비중확대**로 표현되어야 하고, 레버리지 상품의 **변동성 데케이(decay) 위험**을 경고해야 한다. (d) 브리핑은 **분절 캡션이 아니라 하나의 한국어 서사**여야 한다(사용자 선호: 갤러리·브리핑은 한 이야기로 엮기). (e) 예측은 **영속화**되어 최신본을 조회할 수 있고, **워커가 주기적으로 갱신**해야 한다. (f) 무권한 불변식: 예측·포지셔닝은 **표시용**이며 주문 권한을 의미하지 않는다(ADR-001, ADR-010).

## Decision

`domain/prediction/`에 **순수·결정론 종합기**를 도입하여 21개 finding을 데스크 뷰→하우스 예측으로 합성하고, 롱/숏 상품 스탠스(인버스/곱버스)와 단일 서사 브리핑을 산출하며, `market_predictions`에 영속화하고 워커가 30분마다 갱신한다.

1. **결정론적 종합기(`synthesizer.py`).** `synthesize(findings, ...)`는 주어진 finding 집합에 대해 순수·결정론적이다(mock·LLM finding에서 동일 동작, 완전 테스트 가능). 데스크는 투표하고(임팩트×확신, 리드 가중 ×1.5), Chief는 데스크 가중치로 데스크 뷰를 합치며(ADR-016 §5), 국면을 분류하고, 상품 스탠스를 도출하며, 시나리오를 사이징하고, 단일 서사 브리핑을 작성한다. `PredictionService.generate`(`agent_service/prediction.py`)가 `AgentService.run_all`(전 에이전트 **동시** 실행, 각 에이전트는 개별 실패 시 mock 폴백)로 finding을 모아 종합기에 넘긴다.

2. **국면 분류(`regime.py`).** `classify_regime(direction, confidence, vol_high, risk_high, data_ok, top_desk)`이 **9개 `MarketRegime`** 중 하나를 결정론적으로 반환한다 — 예: `data_ok=False` → `DATA_UNCERTAIN`; 약세 + 고위험 + 고확신 → `CRISIS`, 그 외 약세 → `RISK_OFF`; 강세 + 고확신 + 저변동 → `RISK_ON_STRONG`, 고변동 → `RISK_ON_FRAGILE`, top_desk가 `FUNDAMENTAL`이면 `EARNINGS_RALLY`, 아니면 `LIQUIDITY_RALLY`; 중립은 변동성에 따라 `SIDEWAYS_HIGH_VOL`/`SIDEWAYS_LOW_VOL`.

3. **롱/숏 상품 사다리 + 스탠스(`instruments.py`).** `PREDICTION_UNIVERSE` 4종 — `069500` KODEX 200(`LONG_1X`), `122630` KODEX 레버리지(`LONG_2X`), `114800` KODEX 인버스(`INVERSE_1X`), `252670` KODEX 200선물인버스2X(`INVERSE_2X`, **"곱버스"**). `stance_for(kind, direction, confidence, regime)`이 종목별 `Stance(label, rationale, risk_note)`를 반환하며 `label`은 `StanceLabel`(`OVERWEIGHT`/`NEUTRAL`/`UNDERWEIGHT`/`AVOID`)이다. 뷰와 **정합**(약세 뷰의 인버스, 강세 뷰의 롱)하는 상품은 확신도가 높을수록 `OVERWEIGHT`로, **역행**하는 상품은 `UNDERWEIGHT`/`AVOID`로 기운다. 모든 2배 상품(`LONG_2X`, 곱버스 `INVERSE_2X`)은 *"레버리지·일일 리밸런싱에 따른 변동성 손실(데케이) 위험 — 장기 보유 부적합"* 리스크 노트를 달고, 고변동·`CRISIS` 국면에서는 방향이 맞아도 `NEUTRAL`/`AVOID`로 끌린다. 이로써 **약세 뷰가 인버스/곱버스 비중확대로 실행 가능**하다.

4. **단일 서사 브리핑.** `_brief`는 분절 캡션이 아니라 하나의 연속 한국어 서사를 짓는다: 국면 → 하우스 방향·확신도(21개 에이전트를 5데스크로 계층 종합) → 주도 데스크의 핵심 근거 → 리스크 데스크의 경고·무효화 조건 → KODEX 200·레버리지/인버스/곱버스 포지셔닝. `_headline`은 한 줄 요약(약세면 "인버스 우위", 강세면 "인버스 비중축소")을 덧붙인다.

5. **출력 계약(`schemas.py`).** `MarketPrediction`(`PREDICTION_SCHEMA_VERSION="1.0.0"`, `extra="forbid"`)은 `prediction_id`, `as_of`, `horizon`(기본 `D5`), `regime`, `direction`, `confidence`, `data_quality`, `headline`, `brief`, `desk_views`(`DeskView`), `instrument_stances`(`InstrumentStance`), `scenarios`(`Scenario` 3개, 확률 합 1.0), `generated_by`(`"mock"|"llm"`), `agent_count`를 담는다. `generated_by`는 finding을 실제로 만든 런타임이라 종합은 입력 출처에 정직하되 입력 위에서는 결정론적이다.

6. **영속화·엔드포인트·워커.** 새 테이블 `market_predictions`(`PredictionRow`, Alembic `0003_predictions.py`, `0002`→`0003`)에 스칼라 컬럼 + 전체 `payload`(JSON)로 저장된다(`created_at` 인덱스로 "latest"). 엔드포인트(`api/routes/prediction.py`, `/api/v1`): `POST /prediction/run`(전 에이전트 실행→종합→`save_prediction`→`AuditAction.AGENT_RUN` 감사 로그→반환), `GET /prediction/latest`(404 until first run), `GET /brief`(`BriefResponse` — 헤드라인+서사+스탠스), `GET /agents/org`(ADR-016). 워커 잡 `refresh_prediction`이 **30분마다** 예측을 재생성·영속화한다(`worker/scheduler.py`).

7. **무권한·deny-by-default 유지.** 예측·스탠스는 **표시용**이다. `122630`/`114800`/`252670`은 `config/instruments.yml`에서 `tradable=false`이고, 어떤 실제 주문도 별도로 deterministic Risk Engine의 `allowed_instruments` 화이트리스트(ADR-010)를 통과해야 한다. 예측 종합기는 주문 표면을 갖지 않으며 어떤 finding도 주문이 되지 않는다(ADR-001).

## Consequences

- 사용자는 매 실행마다 **하나의 하우스 예측 + 단일 서사 데일리 브리핑**을 얻는다 — 국면, 방향·확신, 롱/인버스/곱버스 포지셔닝, 3개 시나리오가 한 화면·한 이야기로 제시되어 제품 무게중심이 예측·브리핑으로 이동한다.
- 종합이 **결정론적**이라 mock·LLM finding 위에서 동일하게 동작하고 완전히 테스트·재현 가능하다. `generated_by`로 입력 출처를 정직히 보고하면서도(분석은 가변), 합성·확률·포지셔닝은 불변(결정론 코드)이라는 경계가 예측 단계에도 적용된다.
- **약세 뷰가 실행 가능**해졌다 — 단순 "롱 회피"가 아니라 인버스(`114800`)·곱버스(`252670`) 비중확대로 표현되며, 모든 2배 레버리지 상품은 변동성 데케이 리스크 노트를 달고 고변동·위기 국면에서 자동으로 보수화된다(레버리지 ETF의 일일 리밸런싱 손실 반영).
- 브리핑이 **분절 캡션이 아닌 한 서사**라 읽기 쉽고, 주도 데스크·리스크 데스크가 드러나 "왜 이 방향인가"가 설명된다(ADR-016의 데스크 구조 활용).
- 예측이 **영속화·워커 갱신**되어 `POST` 없이도 `/prediction/latest`·`/brief`가 30분 주기로 최신을 유지한다. `market_predictions`가 추가되어 테이블이 10개가 된다(ARCHITECTURE §5).
- 가중치·임계값(데스크 ±0.15, 전체 ±0.12, 확신 밴드 0.35/0.55, 레버리지 보너스 1.5)은 **현재의 합리적 기본값**이다. 시장 변화에 따라 재조정될 수 있으나 결정론적이라 효과가 재현·검증 가능하다.
- **예측이 주문 권한을 의미하지 않는다.** 스탠스는 표시용이고, 실제 매매는 `tradable` 화이트리스트와 deny-by-default Risk Engine을 별도로 통과해야 한다(ADR-010). 무권한 불변식(ADR-001)은 그대로다.

## Alternatives Considered

- **LLM에게 종합·브리핑을 맡김(rejected).** Chief를 실제 LLM으로 두어 21개 finding을 자유 종합·작문시키면 결과가 비결정적·비재현이라 백테스트·감사가 어렵고, 확률·포지셔닝 같은 자금 인접 산출물을 신뢰 불가 출력에 맡기게 된다. 종합은 결정론 코드로 두고 LLM은 입력(finding)만 생성한다(ADR-015 경계 연장).
- **약세를 "롱 회피"로만 표현(rejected).** 인버스/곱버스를 모델링하지 않으면 약세 국면에서 사용자가 취할 행동이 없다("관망"). 롱/숏 레버리지 사다리(`PREDICTION_UNIVERSE`)와 `stance_for`로 약세 뷰를 **인버스/곱버스 비중확대**라는 실행 가능한 스탠스로 번역한다.
- **레버리지 데케이 위험 무시(rejected).** 곱버스·레버리지를 1배 상품과 동일하게 다루면 일일 리밸런싱에 따른 변동성 손실을 사용자가 오해한다. 모든 2배 상품에 데케이 리스크 노트를 강제하고 고변동·`CRISIS`에서 보수화한다.
- **분절 캡션/필드 나열식 브리핑(rejected).** 데스크별 결과를 토막 캡션으로 나열하는 편이 구현은 쉽지만 읽히지 않고 서사가 없다. 국면→방향→주도 근거→리스크→포지셔닝을 잇는 단일 한국어 서사로 작성한다.
- **예측을 영속화하지 않고 매 요청 재계산(considered, not chosen).** 단순하지만 매 조회가 21개 에이전트(특히 LLM 런타임) 실행을 유발해 비싸고 느리다. `market_predictions`에 저장하고 워커가 30분마다 갱신하여 조회는 저장본을 읽는다.
- **국면을 LLM/확률 모델로 산출(considered, not chosen).** 더 정교할 수 있으나 비결정·불투명하다. 규칙 기반 `classify_regime`으로 9개 국면을 결정론적·설명 가능하게 분류하고, 입력 신호(방향·확신·변동성·위험·데이터 품질·top desk)는 종합기에서 도출한다.
