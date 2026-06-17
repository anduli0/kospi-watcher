# ADR-002: Broker Adapter 추상화

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 최종적으로 한국투자증권(KIS), 키움증권(Kiwoom) 등 복수 증권사 Open API와 연결될 수 있다. 각 브로커는 인증 방식, 주문 필드, 호가 응답 형식, 체결 통지 구조가 모두 다르다. 만약 브로커별 API 명세가 전략·도메인 코드에 직접 침투하면, 브로커 교체나 추가 시 도메인 전반을 수정해야 하고, 특정 증권사에 종속(lock-in)된다.

스펙 §2는 "Broker별 API 명세가 전략 코드에 직접 침투하지 않게 한다"(원칙 11), "전략 코드와 브로커 구현은 인터페이스로 분리한다"(원칙 12)를 요구한다. 스펙 §10은 브로커 비종속 `BrokerAdapter` Protocol을 제시하며, 메서드로 `get_quote`, `get_orderbook`, `get_positions`, `get_balance`, `submit_order`, `cancel_order`, `get_executions`를 둔다. 오버레이 E항은 인터페이스 메서드명을 `submit_order(order: ApprovedOrder)`로 고정하고, `submit_order` 구현 위치를 `domain/execution/broker` + `apps/execution-gateway`로 제한한다.

이번 Phase에서는 실거래·실 브로커 연결을 구현하지 않으며(스펙 §10, 오버레이 E), mock만 둔다.

## Decision

브로커 비종속 인터페이스 `BrokerAdapter`를 정의하고, 모든 브로커 상호작용을 이 추상화 뒤로 숨긴다.

1. **Protocol 정의.** `src/kospi_watcher/domain/execution/broker`에 `BrokerAdapter` Protocol을 둔다. 메서드는 스펙 §10을 따른다: `get_quote(symbol)`, `get_orderbook(symbol)`, `get_positions()`, `get_balance()`, `submit_order(order: ApprovedOrder) -> BrokerOrder`, `cancel_order(order_id)`, `get_executions()`. 입출력 타입은 도메인 모델(Quote, OrderBook, Position, AccountBalance, ApprovedOrder, BrokerOrder, Execution)로, 브로커 고유 페이로드를 노출하지 않는다.

2. **submit_order 위치 제한.** `submit_order`의 호출 가능한 정의는 `domain/execution/broker`(인터페이스)와 `apps/execution-gateway`(런타임)에만 존재한다. Agent Service/도메인 agents 계층에는 import 경로가 없다(ADR-001 연계). 이를 AST/문자열 스캔 테스트로 강제한다(스펙 테스트 #8).

3. **MockBrokerAdapter.** 이번 Phase에서는 실제 주문을 수행하지 않는 안전한 `MockBrokerAdapter`/stub만 구현한다. mock 데이터는 "MOCK DATA — NOT REAL MARKET DATA" 배너로 명시하고 실데이터로 위장하지 않는다(오버레이 E).

4. **확장 구조.** 향후 `KISBrokerAdapter`, `KiwoomBrokerAdapter`를 `src/kospi_watcher/adapters/brokers`에 추가하면 도메인/전략 코드 수정 없이 주입(injection)만으로 교체 가능하게 한다. 실제 KIS/Kiwoom API 연결 코드는 이번 Phase에서 작성하지 않는다.

5. **명세 불확실성 원칙.** 공식 API 명세가 불확실하면 추측해 구현하지 않는다(스펙 §2-17). adapter는 typed 경계로만 두고, 실 연동은 명세 확정 후 별도 작업으로 미룬다.

## Consequences

- 전략·도메인 코드가 브로커에 무지(broker-agnostic)해진다. 증권사 추가/교체가 adapter 한 개 추가로 끝난다.
- `submit_order`가 단일 계층(execution-gateway)에만 존재하므로, 주문 제출 경로가 좁고 감사하기 쉬워진다. ADR-001의 LLM-실행 분리가 인터페이스 수준에서도 강제된다.
- mock과 실 adapter가 동일 Protocol을 구현하므로, 테스트는 MockBrokerAdapter로, 운영은 실 adapter로 대체 가능하다(test/prod parity).
- 모든 외부 데이터가 typed adapter를 통해 들어온다는 스펙 원칙(§2-13)과 정합한다.
- 추상화 계층이 한 겹 늘어, 브로커 고유 최적화(예: 특정 증권사 전용 주문 타입)를 즉시 쓰기 어렵다. 필요 시 Protocol 확장 + capability 플래그로 대응한다.

## Alternatives Considered

- **브로커 SDK 직접 호출(rejected).** 전략 코드에서 KIS/Kiwoom SDK를 바로 호출. 가장 빠르지만 스펙 §2-11/12를 정면 위반하고, 증권사 종속과 명세 침투를 초래한다. 기각.
- **얇은 HTTP 클라이언트만 두고 매핑은 호출부에서(rejected).** adapter 없이 httpx 래퍼만 제공하고 응답 매핑을 각 사용처가 처리. 매핑 로직이 코드 전역에 흩어져 브로커 변경 시 산탄총 수정(shotgun surgery)이 발생한다. 기각.
- **추상 기반 클래스(ABC) 상속(considered, not chosen).** Protocol 대신 ABC로 강제 상속. 동작은 유사하나, Protocol은 구조적 타이핑(structural typing)으로 mock·테스트 더블을 더 유연하게 받아들이고 mypy 검증과도 잘 맞아 Protocol을 선택했다.
