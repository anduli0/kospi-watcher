# ADR-014: PAPER(모의) 실행을 안전한 실행 계층으로 구현

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 분석에서 끝나지 않고 "리스크 승인된 제안이 실제로 어떻게 체결되고 포지션·손익으로 이어지는가"를 검증할 수 있어야 한다. 그러나 실거래(LIVE)는 본 Phase에서 의도적으로 비구현이다(ADR-005, TRADING_SAFETY §12). 실 브로커·실 자격증명 없이도 주문 수명주기·포지션·손익 로직을 **안전하게** 행사할 수 있는 실행 계층이 필요하다.

요구사항: (a) 실제 돈을 움직이지 않고 실제 브로커에 접속하지 않는다. (b) 기존 안전 불변식을 우회하지 않는다 — deterministic deny-by-default Risk Engine(ADR-010) 선행, `ApprovedOrder`는 APPROVED `RiskDecision`에서만 생성(ADR-001), 13상태 머신의 불법 전이 금지, idempotency 중복 거부, Audit Log 기록(ADR-006). (c) 손익·평균단가 계산은 `float`가 아닌 `Decimal`(ADR-008). (d) 실행은 다중 게이트 중 하나라도 단독으로 실거래를 켜지 못한다는 원칙을 해치지 않는다. (e) mock/시뮬레이션임이 명확히 라벨링된다.

기존 코드에는 `MockBrokerAdapter`(안전 stub, `mode="MOCK"`)와 `ExecutionGateway`(broker.submit_order의 유일한 외부 호출자)가 있었으나, 제안을 체결·포지션·손익까지 끌고 가는 **오케스트레이션**과 그 영속 모델(orders/fills/positions)이 없었다.

## Decision

PAPER를 "안전한 실행 티어"로 구현한다. 시뮬레이션 체결만 생성하며, 오직 `TRADING_MODE=PAPER`에서만 동작한다. LIVE는 여전히 비구현으로 둔다.

1. **모듈 수준 구현 플래그.** `config.py`에 `PAPER_EXECUTION_IMPLEMENTED = True`를 추가하고 `LIVE_EXECUTION_IMPLEMENTED = False`를 유지한다. 전자는 "PAPER는 구현됐고 안전하다(실돈·실브로커 없음)"를, 후자는 "환경변수만으로 실주문이 나올 수 없다"를 코드로 못박는다.
2. **PaperBrokerAdapter(`domain/execution/paper.py`, `mode="PAPER"`).** 인메모리 모의 브로커. `submit_order`는 합성 `BrokerOrder`(`PAPER-…` id, `SUBMITTED`)를 반환하고 중복 idempotency_key를 거부한다. `simulate_fill(order, reference_price)`는 LIMIT은 지정가로, MARKET은 기준가로 **전량 모의 체결**하며, 기준가 없는 MARKET은 `PaperFillError`를 던진다. 어떤 실 브로커도 호출하지 않는다. 배너: `PAPER BROKER — SIMULATED FILLS, NO REAL ORDERS, NO REAL MONEY`.
3. **TradingService(`trading/service.py`) 오케스트레이션.** `submit_order`가 제안을 모의 체결까지 끌고 가는 유일한 진입점이다. 흐름: 모드 게이트 확인 → idempotency 확인 → 기준가 확보(ADR-013) → Risk Engine 평가 및 영속화 → 주문 행을 PROPOSED로 생성 → (거절 시 RISK_REJECTED 종결) → `ApprovedOrder.from_decision` → RISK_APPROVED → APPROVED → SUBMITTING → 게이트웨이 submit → SUBMITTED → `simulate_fill` → FILLED → 포지션/손익 갱신. 각 전이는 영속화·Audit Log(`ORDER_STATE_TRANSITION`)에 기록된다. `TRADING_MODE`가 PAPER가 아니면 `ExecutionDisabledError`(API에서 HTTP 409). RESEARCH는 주문을 거부한다.
4. **부호 있는 포지션 손익(`domain/execution/position.py`).** `PositionState`(불변 dataclass)는 *부호 있는* `quantity`(롱>0, 숏<0), `|quantity|`당 `avg_cost`, 누적 `realized_pnl`을 담는다. `apply_fill`은 순수 함수다: 증가(또는 개시)는 가중평균단가를 재계산하고, 감소는 청산 수량에 대해 실현손익을 적립하며, 포지션을 초과하는 체결은 방향을 뒤집고 잔량을 체결가로 재기준화한다. 전부 `Decimal`(ADR-008), I/O·`float` 없음.
5. **새 테이블(마이그레이션 `0002_paper_trading.py`, revision `0002`, down `0001`).** `orders`(주문+수명주기; unique `idempotency_key`), `fills`(체결; FK→`orders.id`; `liquidity="PAPER"`), `positions`(**복합 PK `(account, symbol)`**; 부호 quantity·avg_cost·realized_pnl). 금액은 `DecimalString`(TEXT), 시각은 `DateTime(timezone=True)`로 SQLite/Postgres 양립(ADR-003).
6. **게이트웨이 게이팅(`execution_gateway/gateway.py`).** `ExecutionGateway.submit`은 시뮬레이션 브로커(`MOCK`/`PAPER`)를 허용한다(PAPER는 추가로 `PAPER_EXECUTION_IMPLEMENTED` 필요). 비시뮬레이션(=LIVE) 브로커는 `LIVE_EXECUTION_IMPLEMENTED and live_execution_armed`가 모두 참이 아닌 한 `GatewayBlockedError`로 차단되며, 본 Phase에서 둘 다 거짓이다.
7. **엔드포인트(`api/routes/trading.py`).** `POST /api/v1/orders`(제출; RESEARCH에서 409), `GET /api/v1/orders`, `GET /api/v1/orders/{id}`(체결 포함), `GET /api/v1/positions`(라이브 quote로 마킹), `GET /api/v1/account`(실현/미실현/총 손익·총노출 집계).

## Consequences

- 실 브로커·실 자격증명 없이도 주문 수명주기·포지션·손익을 end-to-end로 행사·검증할 수 있다. 더 중요한 것은, PAPER가 안전 게이트를 **우회하지 않고 그대로 통과**한다는 점이다 — Risk Engine 선행, APPROVED-전용 `ApprovedOrder`, 상태 머신, idempotency, Audit Log가 모두 적용된다.
- `TRADING_MODE=PAPER` 단일 게이트로 실행이 한정되고 기본값 RESEARCH에서는 체결조차 생성되지 않으므로, 우발적 실행 위험이 낮다. 게이트웨이는 시뮬레이션 브로커만 허용하고 LIVE 브로커를 구조적으로 차단한다.
- 손익/평균단가가 순수 `Decimal` 함수(`apply_fill`)로 계산되어 단위 테스트·재현이 쉽고, 부호 있는 포지션으로 롱/숏·플립을 일관되게 다룬다.
- 체결은 **시뮬레이션**이다 — 실제 시장 미시구조(부분체결·슬리피지·호가 스프레드·거부)를 모사하지 않고 전량 즉시 체결한다. 따라서 PAPER 손익은 근사이며, 실거래 기대치로 직결해석하면 안 된다. 후속 Phase에서 실 브로커 모의투자 계좌·부분체결·체결 지연 모델을 도입할 여지를 남긴다.
- LIVE는 여전히 비구현이다. PAPER 구현이 ADR-005(PAPER/LIVE 분리)·TRADING_SAFETY §12의 "실거래 비구현" 원칙을 바꾸지 않으며, `LIVE_EXECUTION_IMPLEMENTED=False`가 이를 보증한다.

## Alternatives Considered

- **실 증권사 모의투자(paper) 계좌 연동(rejected, 현 Phase).** 시장 미시구조를 더 현실적으로 모사하나, 실 자격증명·브로커 API 연동이 필요해 본 Phase 범위(TRADING_SAFETY §12)를 벗어난다. 인메모리 시뮬레이션으로 시작하고, 실 모의투자 연동은 후속 Phase로 둔다.
- **Risk Engine을 건너뛰는 별도 PAPER 경로(rejected).** "모의니까 빠르게"라며 리스크 게이트를 우회하는 경로를 두면, 검증 대상이 실제 안전 경로와 달라지고 우회 습관이 생긴다. PAPER도 동일한 deny-by-default 게이트를 통과하게 한다.
- **손익 계산에 `float` 사용(rejected).** 빠르지만 ADR-008을 위반하고 대사·한도 판단을 부정확하게 만든다. `Decimal` 순수 함수로 강제한다.
- **부호 없는 quantity + 별도 방향 필드(considered, not chosen).** 직관적일 수 있으나 플립(롱↔숏 전환)·평균단가 재기준화 로직이 분기로 복잡해진다. 부호 있는 quantity로 청산/적립/플립을 한 함수에서 일관 처리한다.
- **게이트웨이가 PAPER도 차단(considered, not chosen).** 가장 보수적이나, 그러면 안전한 모의 실행조차 불가능해 검증 목적을 달성하지 못한다. 시뮬레이션 브로커(MOCK/PAPER)만 허용하고 LIVE만 차단하는 절충을 택한다.
