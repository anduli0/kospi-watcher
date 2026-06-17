"""Static catalog of the 21 analysis agents.

Each :class:`AgentSpec` carries the metadata the mock runtime needs to emit a
schema-valid finding. Real Anthropic-backed implementations replace the mock in
a later phase; the catalog (names, versions, categories) stays the contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from kospi_watcher.domain.enums import Horizon, Impact, MarketDirection

AGENT_VERSION = "0.1.0"


@dataclass(frozen=True)
class AgentSpec:
    name: str
    version: str
    category: str
    summary: str
    direction: MarketDirection
    impact: Impact
    horizon: Horizon
    sectors: tuple[str, ...] = ()


_B = MarketDirection.BULLISH
_S = MarketDirection.BEARISH
_N = MarketDirection.NEUTRAL
_LO, _ME, _HI = Impact.LOW, Impact.MEDIUM, Impact.HIGH

AGENT_CATALOG: tuple[AgentSpec, ...] = (
    AgentSpec("Market Data Integrity Agent", AGENT_VERSION, "DATA_INTEGRITY",
              "시세·수급·지표 데이터의 결측/지연/이상치 무결성 점검", _N, _ME, Horizon.INTRADAY),
    AgentSpec("News Deduplication Agent", AGENT_VERSION, "NEWS",
              "동일 사건 뉴스 군집화 및 중복 제거", _N, _LO, Horizon.INTRADAY),
    AgentSpec("Source Verification Agent", AGENT_VERSION, "NEWS",
              "출처 신뢰도 검증 및 미검증 주장 격리", _N, _ME, Horizon.INTRADAY),
    AgentSpec("Disclosure and Corporate Event Agent", AGENT_VERSION, "DISCLOSURE",
              "DART 공시·기업 이벤트 영향 분석", _N, _ME, Horizon.D1),
    AgentSpec("Korea Macro Agent", AGENT_VERSION, "MACRO",
              "한국 성장·물가·고용·수출·한국은행 정책 분석", _B, _ME, Horizon.D20),
    AgentSpec("Global Growth Agent", AGENT_VERSION, "MACRO",
              "미국·중국 등 글로벌 경기와 위험선호 분석", _B, _ME, Horizon.D20),
    AgentSpec("Rates and Liquidity Agent", AGENT_VERSION, "MACRO",
              "연준·금리·글로벌 유동성 흐름 분석", _S, _HI, Horizon.D20),
    AgentSpec("FX Agent", AGENT_VERSION, "MACRO",
              "원/달러 환율과 수출주·외국인 수급 민감도 분석", _S, _ME, Horizon.D5),
    AgentSpec("Commodity and Energy Agent", AGENT_VERSION, "MACRO",
              "유가·원자재·에너지 가격이 섹터에 미치는 영향 분석", _N, _ME, Horizon.D5),
    AgentSpec("Geopolitics and Trade Agent", AGENT_VERSION, "GEOPOLITICS",
              "국제정세·무역분쟁·제재·공급망 리스크 분석", _S, _HI, Horizon.D5),
    AgentSpec("Foreign and Institutional Flow Agent", AGENT_VERSION, "FLOW",
              "외국인·기관·개인 투자자별 수급 분석", _B, _HI, Horizon.D1),
    AgentSpec("Derivatives and Program Agent", AGENT_VERSION, "FLOW",
              "프로그램 매매·선물 베이시스·옵션 포지션 분석", _N, _ME, Horizon.INTRADAY),
    AgentSpec("Breadth and Technical Agent", AGENT_VERSION, "TECHNICAL",
              "시장 폭·추세·모멘텀·신고저가 기술적 분석", _B, _ME, Horizon.D5),
    AgentSpec("Volatility and Regime Agent", AGENT_VERSION, "REGIME",
              "변동성 국면과 9개 레짐 분류 신호 산출", _N, _HI, Horizon.D1),
    AgentSpec("Earnings and Valuation Agent", AGENT_VERSION, "FUNDAMENTAL",
              "이익 추정치 변화와 밸류에이션 분석", _B, _ME, Horizon.D20),
    AgentSpec("Technology and Semiconductor Agent", AGENT_VERSION, "SECTOR",
              "반도체·IT 사이클과 수출 모멘텀 분석", _B, _HI, Horizon.D20,
              ("반도체", "IT하드웨어", "소프트웨어")),
    AgentSpec("Industrial and Export Agent", AGENT_VERSION, "SECTOR",
              "조선·기계·자동차 등 수출 제조업 분석", _B, _ME, Horizon.D20,
              ("조선", "기계", "자동차")),
    AgentSpec("Domestic Demand and Defensive Agent", AGENT_VERSION, "SECTOR",
              "내수·필수소비재·통신·유틸리티 방어주 분석", _N, _LO, Horizon.D20,
              ("필수소비재", "통신", "유틸리티")),
    AgentSpec("Structural Growth Scout", AGENT_VERSION, "STRUCTURAL",
              "AI·전력·원전·방산·로봇 등 장기 성장 산업 탐색", _B, _HI, Horizon.STRUCTURAL,
              ("AI", "전력기기", "원전", "방산", "로봇")),
    AgentSpec("Red-Team and Risk Agent", AGENT_VERSION, "RISK",
              "낙관 시나리오 반증·꼬리위험·투자논거 무효화 조건 점검", _S, _HI, Horizon.D5),
    AgentSpec("Chief Market Synthesizer", AGENT_VERSION, "SYNTHESIS",
              "전 에이전트 결과 종합 및 시장 국면·전망 합성", _N, _HI, Horizon.D5),
)

assert len(AGENT_CATALOG) == 21, "the agent catalog must contain exactly 21 agents"  # noqa: S101
