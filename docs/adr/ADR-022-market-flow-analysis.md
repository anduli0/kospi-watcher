# ADR-022: 시장 흐름 분석 — 섹터 등락 + 투자자 수급(외국인/기관/개인)

## Status

Accepted (2026-06-17)

## Context

기존 화면은 예측 리포트(ADR-017)·뉴스 브리프(ADR-020)·시세(ADR-013)를 제공하지만, "**오늘 코스피를 움직인 게 무엇인가**"를 한눈에 보여주는 면이 없었다. 이용자(증시 트레이딩)는 (1) 어떤 **산업 섹터**가 지수를 끌고/눌렀는지, (2) **외국인·기관·개인** 수급이 어디로 흐르는지를 일상적으로 본다. 이를 별도 분석 섹션으로 추가하되, 안전·정직 불변식(실데이터는 정직히 소싱, mock은 라벨링, float 금지, 표시 전용)을 유지해야 했다.

데이터 가용성이 비대칭이다: **섹터 등락**은 KODEX 산업 ETF를 통해 키리스 Yahoo로 실시간 산출이 가능하다. 그러나 **투자자별 순매수(외국인/기관/개인)**는 신뢰할 만한 키리스 실시간 피드가 없다(KRX OTP/pykrx는 별도 연동·취약). 한쪽은 실데이터, 한쪽은 당장은 불가한 상황에서 화면을 어떻게 정직하게 채울지가 쟁점이었다.

## Decision

**섹터 보드는 Yahoo 실데이터로, 투자자 수급은 '대표값(representative)'으로 분리 소싱**하고 각각 출처를 라벨링한다. 순수 도메인 스키마 + 인프라 서비스 + 단일 읽기 라우트로 구성한다.

1. **도메인 스키마(순수).** `domain/market_analysis/schemas.py`에 `SectorMove`(key·name·symbol·price·`change_pct`·source), `InvestorTrendPoint`(date·net), `InvestorFlow`(investor·label·net_today·net_5d·trend·source), `MarketAnalysis`(index·sectors·leaders·laggards·flows·narrative·sector_source·flow_source)를 둔다. 금액·등락률은 모두 `Decimal`/`DecimalNoFloat`(float 금지, ADR-008), 시각은 aware(ADR-009).
2. **섹터 = Yahoo 실시간(키리스).** `infrastructure/marketdata/analysis.py`의 `MarketAnalysisService`가 8개 KODEX 산업 ETF(반도체·2차전지·은행·자동차·바이오·철강·운송·에너지화학)와 `^KS11`을 Yahoo chart 엔드포인트로 조회한다. 일간 등락률은 `regularMarketPrice` 대비 **`previousClose`**(없으면 `chartPreviousClose`)로 산출하고 `range=1d`로 요청한다(전전일과 비교되어 변동이 부풀려지지 않도록). 제공자(yahoo.py)와 동일하게 **never-raises**: 개별 섹터 조회 실패 시 라벨된 오프라인 값(`source="mock"`)으로 강등하고, 과반 실패 시 `sector_source="mock"`로 보고한다. 짧은 TTL 캐시로 새로고침이 Yahoo를 난타하지 않게 한다.
3. **투자자 수급 = 대표값(representative), 명시적 라벨.** 키리스 실시간 KRX 피드가 없으므로, 외국인/기관/개인 순매수는 **KST 날짜로 결정론적으로 생성한 대표값**이다(`source="representative"`). 세 그룹은 매일 합이 ≈0(개인이 외국인+기관의 반대 매매 상대) — 거래소 수급의 제로섬 성격을 반영한다. 당일 외국인 부호는 **지수 방향과 정합**하도록 바이어스를 줘 내러티브가 어긋나지 않는다. 이는 실제 KRX 집계가 아니며, 스키마(`flow_source`)와 UI 배지·고지문에 분명히 표기한다. 후속으로 KRX/pykrx 실데이터를 이 지점에 끼우면 자동 대체된다.
4. **단일 읽기 라우트.** `GET /api/v1/market/analysis`가 `MarketAnalysisService().build()` 결과(`MarketAnalysis` 도메인 스키마를 그대로 response_model로 재사용 — `RiskDecision` 재사용 선례와 동일)를 반환한다. 표시 전용이며 주문 권한과 무관하다.
5. **웹 `/market` 페이지 + nav "시장".** 코스피 지수·내러티브, 섹터별 다이버징 바(강세=빨강/약세=파랑, 한국 관례), 외국인·기관·개인 카드(당일·5일 누적·5거래일 미니 추이)와 **수급 출처 고지**를 렌더한다. nav/홈 배너에 `lucide-react` 아이콘을 절제된 톤으로 추가한다.

## Consequences

- 이용자는 "오늘 코스피를 움직인 섹터"와 "투자자 수급 방향"을 한 화면에서 본다. 섹터는 실시간 실데이터라 즉시 유용하다.
- 정직성 유지: 섹터는 `source="yahoo"`(실패 시 mock 라벨), 수급은 `source="representative"`로 명시되어 실데이터로 오인될 수 없다. mock/representative 라벨링 불변식과 일관된다.
- float 미사용·aware 시각·표시 전용 원칙을 그대로 지켜 트레이딩 안전 불변식을 건드리지 않는다.
- 수급은 당장 대표값이라는 한계가 있으나, 인터페이스(`InvestorFlow`/`flow_source`)가 고정돼 있어 KRX/pykrx 실데이터 연동 시 UI 변경 없이 교체된다.

## Alternatives Considered

- **수급도 pykrx로 실데이터(considered, not chosen·후속).** 즉시 정확하지만 동기·취약(OTP 의존)하고 의존성·지연을 추가한다. 인터페이스를 먼저 고정하고 대표값으로 출시한 뒤, 안정적 연동을 후속으로 둔다.
- **섹터를 mock 고정값으로(rejected).** Yahoo로 실데이터가 가능한데 mock으로 두는 것은 정직성·유용성 모두 손해다.
- **예측/오늘 페이지에 끼워 넣기(considered, not chosen).** 정보량이 많아 전용 `/market` 페이지가 가독성에 유리하고, 홈 배너로 진입을 노출한다.
- **섹터 등락률을 `range=2d`로 계산(rejected).** 전전일 종가와 비교되어 일간 변동이 과대 계상된다. `range=1d` + `previousClose`로 정확한 일간 변동을 쓴다.
