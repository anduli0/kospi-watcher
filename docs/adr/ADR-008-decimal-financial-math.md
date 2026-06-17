# ADR-008: Decimal 기반 금융 계산 (float 금지)

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 가격, 수량, 금액, 평균단가, 실현·미실현 손익, 노출·한도, 슬리피지 등을 계산한다. 이진 부동소수점(float)은 0.1 같은 십진 소수를 정확히 표현하지 못해 누적 오차가 발생한다. 금융 계산에서 이런 오차는 잔고 불일치, 대사(reconciliation) 실패, 리스크 한도 오판으로 이어질 수 있고, 한국 주식·ETF의 호가 단위(tick size)·체결 금액을 정확히 다루지 못하면 주문 자체가 틀어진다.

스펙 §9는 "금액, 가격, 수량 계산에는 float 대신 Decimal을 사용한다"를 명시하고, 오버레이 E항은 money/price를 SQLAlchemy `Numeric`, Pydantic `Decimal`로 두고 float를 금지한다. 스펙 테스트 #1은 "Money 및 Price에 float가 사용되지 않는지 검사"를 요구한다. 또한 ADR-003에 따라 단일 마이그레이션 이식성을 위해 DB 타입은 `Numeric`을 사용한다.

## Decision

모든 금융 수치(money/price/quantity 및 그 파생값)는 **Python `Decimal`** 로 표현·계산하고, **float를 금지**한다.

1. **도메인·API 타입.** money/price/quantity 필드는 Pydantic 모델에서 `Decimal`로 선언한다. float가 흘러들면 검증 단계에서 거부한다(스펙 테스트 #1). 직렬화/역직렬화도 Decimal 정밀도를 보존하도록 한다(JSON에서는 문자열 기반 직렬화를 권장).
2. **DB 타입.** SQLAlchemy 컬럼은 `Numeric`을 사용한다(부동소수점 컬럼 금지). 이는 SQLite·PostgreSQL 양립 마이그레이션(ADR-003)과도 정합한다.
3. **계산 규약.** 금융 계산은 Decimal 컨텍스트에서 수행하고, 반올림은 명시적 규칙(예: 호가 단위·통화 단위에 맞춘 quantize/ROUND_HALF_UP 등)을 사용한다. float와의 혼산(mixed arithmetic)을 피한다.
4. **검증 강제.** "Money/Price에 float가 사용되지 않는지" 검사하는 테스트를 두어, 모델·계산 경로에 float가 새어들지 않음을 CI에서 회귀 방지한다.
5. **경계에서의 변환.** 외부 데이터(문자열/숫자)가 들어올 때 typed adapter 경계에서 Decimal로 변환하고, float를 거쳐 정밀도가 손실되지 않게 한다.

## Consequences

- 십진 정밀도가 보존되어 잔고·손익·한도 계산이 정확해지고, 대사 실패·리스크 오판 위험이 줄어든다.
- DB(`Numeric`)·도메인(`Decimal`)·API(`Decimal`)가 일관된 정밀도를 공유한다. ADR-003의 이식 가능한 단일 마이그레이션과도 맞물린다.
- Decimal은 float보다 연산이 느리고 메모리를 더 쓴다. 고빈도 계산에서 비용이 있으나, 금융 정확성을 위해 수용한다. 핫패스가 문제되면 국소적으로 정수 최소단위(minor unit) 연산을 고려한다.
- 직렬화 시 Decimal을 부주의하게 float로 변환하면 정밀도가 깨지므로, 직렬화 경로 전반에서 규율이 필요하다.
- 반올림 규칙을 명시하지 않으면 미묘한 불일치가 생기므로, quantize/반올림 정책을 도메인 규약으로 못박는다.

## Alternatives Considered

- **float(double) 사용(rejected).** 가장 빠르고 단순하나, 이진 부동소수점 오차로 금융 계산이 부정확해진다. 스펙 §9와 테스트 #1을 정면 위반. 기각.
- **정수 최소단위(minor units, 예: 전 단위)로 통일(considered, not chosen).** 모든 금액을 정수로 다뤄 오차를 원천 차단. 매우 정확·빠르나, 가격/수량/비율이 다양한 소수 자릿수를 갖는 한국 시장에서 단위 관리가 번거롭고 API/DB 표현이 직관성을 잃는다. 스펙이 Decimal을 명시하므로 Decimal을 기본으로 두고, 필요 시 핫패스에서만 정수 연산을 국소 적용한다.
- **십진 라이브러리(예: 외부 money 라이브러리) 도입(considered, not chosen).** 통화·반올림을 캡슐화한 money 라이브러리 사용. 편의는 있으나 의존성·러닝커브가 늘고 Pydantic/SQLAlchemy와의 정합을 별도로 맞춰야 한다. 표준 `Decimal` + `Numeric` 조합으로 충분하여 채택하지 않았다.
