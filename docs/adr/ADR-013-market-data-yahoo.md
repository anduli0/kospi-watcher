# ADR-013: 키리스(keyless) Yahoo Finance 시세 provider + mock 폴백

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER의 리스크·매매 경로는 가격 컨텍스트를 필요로 한다. Risk Engine의 가격 이탈(price deviation) 체크는 기준가(reference/last price)가 있어야 의미가 있고, PAPER 실행(ADR-014)은 MARKET 주문 체결가와 포지션 마킹(mark-to-market)에 현재가가 필요하다. 그러나 본 Phase에는 실 증권사(KIS/Kiwoom) 연동이 없고(TRADING_SAFETY §12), 그 브로커 키도 없다. 따라서 "주문 권한과 무관한 읽기 전용 시세"만이라도 실데이터로 공급할 수 있어야 한다.

제약과 요구사항은 다음과 같다. (a) **키 없이** KOSPI 지수·USD/KRW·거래 대상 KOSPI200 ETF의 시세를 얻어야 한다(벤더 락인·계약·비밀 운영 부담 회피). (b) 시세 소스 장애가 리스크/매매 경로를 **절대 터뜨리면 안 된다**(fail-safe, TRADING_SAFETY §1). (c) 가격은 `float`가 아니라 `Decimal`이어야 한다(ADR-008). (d) 시각은 timezone-aware여야 한다(ADR-009). (e) mock 데이터는 실데이터로 **오인될 수 없도록 라벨링**되어야 한다(TRADING_SAFETY §12.3, "honesty about state"). (f) 오프라인/CI에서 네트워크 없이 결정론적으로 테스트 가능해야 한다.

Yahoo Finance의 공개 차트 엔드포인트(`https://query1.finance.yahoo.com/v8/finance/chart/<symbol>`)는 API 키 없이 호출되며, `User-Agent` 헤더만 있으면(없으면 HTTP 429) 지수·환율·국내 ETF의 정규장 가격을 반환한다. 이는 위 요구를 키 없이 충족할 수 있는 실용적 소스다.

## Decision

키리스 Yahoo provider를 기본 시세 소스로 채택하고, 결정론적 mock을 폴백/오프라인 소스로 둔다. provider는 **결코 예외를 던지지 않는다**.

1. **공용 provider 추상화.** `infrastructure/marketdata/base.py`에 `Quote`(`symbol`, `price`=`DecimalNoFloat`, `currency`, `as_of`=`AwareDatetime`, `source`, `stale`)와 `MarketDataProvider` Protocol(`get_quote`/`get_quotes`)을 둔다. 시스템 전체는 *내부 심볼*(`KNOWN_SYMBOLS = ("069500","102110","229200","KOSPI","USDKRW")`)만 알고, 각 provider가 자신의 벤더 심볼로 매핑한다.
2. **Never-raise 계약.** Protocol 문서에 명시하듯 구현은 `get_quote`/`get_quotes`에서 **절대 raise하지 않는다**. 실패 시 `None`을 반환(또는 해당 심볼 누락)하여 Risk/Trading 경로가 안전하게 강등(degrade)되게 한다. "판단 불가 = 가격 없음"이지 "예외로 경로 중단"이 아니다.
3. **YahooMarketDataProvider(keyless).** 공개 차트 엔드포인트를 호출하고, 내부→Yahoo 심볼을 매핑한다(`069500→069500.KS`, `102110→102110.KS`, `229200→229200.KS`, `KOSPI→^KS11`, `USDKRW→KRW=X`). `User-Agent` 헤더(설정값 `market_data_user_agent`)를 보내고, 결과를 짧은 TTL(`market_data_ttl_seconds`, 기본 60초) 동안 캐시한다. HTTP 비200·전송오류·파싱오류 시 마지막 캐시값을 `stale=True`로 반환하거나, 없으면 `None`을 반환한다. 가격은 `to_decimal(str(price))`로 `Decimal` 변환한다(`float` 미경유). `httpx.AsyncClient`는 주입 가능(테스트용).
4. **MockMarketDataProvider(라벨링).** 고정·합리적 가격을 `source="mock"`·`stale=True`로 반환하고 네트워크를 건드리지 않는다. 라벨링으로 실데이터 오인을 차단한다.
5. **팩토리 + 설정 스위치.** `factory.get_market_data_provider()`가 `market_data_provider`(기본 `"yahoo"`, 그 외 `"mock"`) 설정으로 backend를 선택하고 프로세스 전역 싱글턴을 캐시한다. `reset_market_data_provider()`로 테스트에서 폐기한다.
6. **소비처.** `GET /api/v1/market/quotes`가 `MarketQuotesResponse`를 반환한다. `POST /api/v1/risk/evaluate`는 명시 `last_price` → 라이브 quote → 제안가(`effective_price`) 순으로 기준가를 채워 이탈 체크가 항상 동작하게 한다. PAPER 경로(ADR-014)는 동일 provider로 포지션을 마킹하고 MARKET 체결가를 산정한다. `/system/status`는 활성 provider를 데이터 소스로 보고한다(`market-data:<provider>`).

## Consequences

- 키·계약·벤더 락인 없이 KOSPI/USDKRW/ETF 실시세를 확보한다. 비밀 운영 부담이 없고, 소스 교체(다른 provider 추가)는 `MarketDataProvider` Protocol 구현만으로 가능하다.
- never-raise 계약 + TTL 캐시 + stale 플래그로 시세 장애가 리스크/매매 경로를 멈추지 않는다. 장애 시 낡은 가격은 `stale=True`로 정직히 표기되어, 호출자가 신선도를 판단할 수 있다(Risk Engine의 호가/데이터 최신성 체크와 연동 가능).
- `Decimal`(ADR-008)·`AwareDatetime`(ADR-009)을 경계에서 강제하므로 정밀도/시각 규율이 유지된다. mock은 항상 라벨링되어 실데이터로 위장되지 않는다(TRADING_SAFETY §12.3).
- Yahoo 공개 엔드포인트는 비공식·무SLA다. 레이트리밋(429)·스키마 변경·일시 장애 가능성이 있으며, 본 ADR은 이를 캐시·폴백·`None` 반환으로 완충할 뿐 가용성을 보장하지 않는다. 운영 등급 신뢰가 필요하면 후속 Phase에서 정식 데이터 벤더/브로커 피드로 대체한다. 이는 읽기 전용 시세에 한하며 **주문 권한과 무관**하다.
- 시세는 실데이터지만 KIS/Kiwoom 등 **브로커·공시·거시 피드는 여전히 미연동 placeholder**다(`/system/status`에서 `not_configured`). 시세 도입이 실거래(LIVE) 비구현 원칙을 바꾸지 않는다.

## Alternatives Considered

- **실 증권사(KIS/Kiwoom) 시세 API 사용(rejected, 현 Phase).** 정확·공식이나 키·계약·비밀 운영이 필요하고, 본 Phase의 "실 브로커 미연동" 범위(TRADING_SAFETY §12)를 벗어난다. 읽기 전용 시세는 키리스 Yahoo로 시작하고, 브로커 연동은 후속 Phase로 미룬다.
- **유료 데이터 벤더(키 필요) 도입(considered, not chosen).** SLA·품질은 좋으나 비용·키 관리·벤더 락인이 따른다. provider 추상화를 둔 만큼, 필요해지면 새 구현을 추가하면 되므로 지금은 채택하지 않는다.
- **provider가 실패 시 예외를 던지도록(rejected).** 단순하지만 시세 장애가 리스크/매매 경로를 중단시켜 fail-safe 원칙(TRADING_SAFETY §1)에 반한다. never-raise + `None`/stale 폴백으로 대체한다.
- **가격을 `float`로 취급(rejected).** 빠르지만 ADR-008(금융 계산 float 금지)을 정면 위반한다. `Decimal`(문자열 경유)로 강제한다.
- **시세 없이 제안가만으로 리스크 평가(considered, not chosen).** 외부 의존이 없어 단순하나, 가격 이탈 체크가 사실상 무력화되고 PAPER MARKET 체결가를 산정할 수 없다. 라이브 기준가를 우선하되 제안가로 폴백하는 절충을 택한다.
