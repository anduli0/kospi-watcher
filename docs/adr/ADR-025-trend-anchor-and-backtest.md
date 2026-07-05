# ADR-025: 가격 추세 앵커 + 방향 정확도 백테스트 (예측의 시장 정합 + 정직한 측정)

## Status

Accepted (2026-06-18)

## Context

ADR-024에서 BOK 통화정책을 핵심 변수로 반영한 직후 사용자는 **"이 예측의 정확도를 시뮬레이션하고 정확도를 높일 방법을 찾으라"**고 요청했다. 측정해 보니 두 가지 문제가 드러났다.

1. **결정론적 mock 에이전트는 날짜와 무관하다.** 같은 환경·같은 BOK 입력이면 항상 같은 출력을 낸다. 시장이 강세 추세에 있어도 BOK 매파가 결정적이면 하우스 뷰가 약세로 굳어, **실제 시장과 정면 충돌**한다. 이 경우 D20 기준 기저율(test 81.5%) 정도의 확률로 방향이 틀린다.
2. **단순 가격 신호로 5일 방향을 맞히는 건 본질적으로 어렵다.** 실데이터(^KS11 5년) 백테스트에서 어떤 후보(모멘텀·MA·MA크로스·triple)도 D5 train 50% 미만이었고, D20도 단순 기저율 대비 +2~3%p 스킬이 최대였다(균형장 기준). 강세장이 지배한 test 기간은 "항상 상승" 기저율 81~94%라 어떤 신호도 그걸 못 이긴다 — 이는 시장 국면의 특성이지 신호의 결함이 아니다.

목표: (a) **실제 시장 추세에 하우스 뷰를 정합**시켜 BOK가 흐름을 거스를 때도 시장을 거스르지 않게 하고, (b) **정확도를 정직히 측정·표시**하는 백테스트 서피스를 둔다. 결정론·표시전용·정직 소싱·float미사용 불변식은 그대로 유지.

## Decision

**가격 추세 신호를 예측의 주 앵커(primary anchor)로 도입**하고, 같은 신호 함수의 **out-of-sample 정확도를 백테스트해 정직히 공개**한다.

1. **순수 추세 신호**(`domain/prediction/trend_signal.py`). `trend_core(closes, i)`는 시점 i까지의 데이터만으로(미래 정보 누설 없이) `(direction{-1,0,1}, strength, sma100, mom60)`을 산출한다: 100일 SMA 대비 위치(±0.5% 밴드 내면 무추세) + 60일 모멘텀과 부호 일치(불일치 시 abstain). 시장 국면 정합성과 균형장 양의 스킬을 동시에 만족하는 트레이드오프로 후보(MA200, triple, no-abstain 등) 중 채택. 같은 함수가 백테스트·예측 양쪽에 쓰여 **측정된 게 실제 사용되는 신호**다.
2. **FLOW_TECH 데스크 주입 + 수석 틸트**. `apply_trend_to_findings`가 FLOW_TECH의 **Breadth and Technical Agent** finding을 추세 신호로 덮어써 논의 스레드에 가시화한다. 수석 레벨에서는 `_trend_tilt`(±0.35 한도, 강도 비례)로 **BOK 정책 틸트보다 강하게** 하우스 점수를 시장 추세 쪽으로 끌어준다 — 추세가 주, BOK는 리스크 틸트.
3. **읽기 라우트 + UI**. `MarketPrediction.trend_signal`·`InstrumentAnalysisReport.trend_signal` 필드. UI에 `TrendSignalCard`(주가/100일선/60일 모멘텀/강도/출처)를 `/analysis`·`/prediction` 하우스뷰에 배치.
4. **백테스트**(`domain/prediction/backtest.py`, `agent_service/backtest_service.py`). 5년 일봉(`infrastructure/marketdata/history.py`, 키리스 Yahoo, never-raises·mock 폴백)을 받아 같은 `trend_core`를 D5/D20/D60 horizon에 적용해 **train/test 분리 정확도**를 측정: 방향 적중률, **`naive = max(base_up, 1-base_up)` 기저율**, 스킬, 커버리지. 결과를 `GET /api/v1/backtest`로 노출. **해석(`interpretation`)은 train 기준**으로 verdict를 내고 test 기간의 강세 편향을 명시적으로 설명한다(스킬 음수가 신호 결함이 아니라 국면 특성임을 정직히).
5. **UI**. `BacktestCard`(horizon별 hit/base/skill 카드 3개 + 1개월 주 horizon 요약 + 정직한 해석문)를 `/analysis`에 둔다.

## Consequences

- **시장 정합성**: 이전엔 BOK 매파만으로 약세였던 하우스 뷰가 추세(현재 강세, 강도 100%) 앵커로 **강세·취약한 위험선호**로 정정됐다 — 시장 추세(D20 기저율 81%)와 정합. 종목: 롱 비중확대, 인버스 회피.
- **정직한 정확도**: D20 train **+2.5%p 스킬**(55.5% vs 53.0% 기저율)로 균형장 엣지가 양수임을 검증했고, test의 음수 스킬은 강세장 기저율 때문임을 카드/해석문으로 명시. 과대광고 없이 한계를 인정.
- **결정론·표시전용 유지**: 가격 신호는 순수·과거 한정, 백테스트도 순수. 안전 불변식 불변. 신호 함수가 예측·측정 양쪽에 공유되어 **측정된 게 실제 사용된다**.
- **한계**: 단기 방향 예측은 본질적으로 동전던지기에 가깝고 강세장 기저율을 넘기는 매우 어렵다. 추세 앵커의 가치는 적중률 자체보다 시장 정합·포지셔닝의 신뢰도에 있다.

## Alternatives Considered

- **mock 출력을 그대로 두고 BOK만 강화(rejected).** ADR-024 직후 상태로 시장과 충돌해 정확도가 떨어진다 — 사용자 요청과 정면 모순.
- **여러 추세 신호 후보(simpler/200MA/triple/long) 채택(rejected).** train 스킬에서 current가 +3.0%p로 최고(다른 후보는 +0.2~+2.8%p). 단순함과 train 스킬 양립.
- **horizon별 다른 신호 사용(considered, not chosen·후속).** D20·D60에 별도 신호를 둘 수 있지만 인터페이스 복잡도 증가. 현 단일 신호로 시작.
- **LLM에 정확도 측정 위임(rejected).** 비결정론·비용·환각. 결정론 백테스트가 정직성·재현성에서 우월.
- **test에서 스킬 음수면 신호 폐기(rejected).** test 기간 기저율 81% 시장에서 어떤 신호도 못 이긴다는 게 백테스트의 본질적 진실이고, 균형장 train에서 +2.5%p 양의 스킬이 검증된 신호를 폐기하는 건 통계적으로 옳지 않다.
