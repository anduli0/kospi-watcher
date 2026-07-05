"""Builds the per-instrument analysis report (ADR-023).

Combines the latest house prediction (direction / confidence / regime) with live
prices for the long/inverse/leveraged ladder and runs the deterministic
:func:`build_report` projection. If no prediction is stored yet, it generates one
on the fly (mock runtime) so the analysis surface always renders.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.agent_service.prediction import PredictionService
from kospi_watcher.db import repositories
from kospi_watcher.domain.prediction.instrument_outlook import (
    InstrumentAnalysisReport,
    build_report,
)
from kospi_watcher.domain.prediction.instruments import PREDICTION_UNIVERSE
from kospi_watcher.domain.prediction.schemas import MarketPrediction
from kospi_watcher.domain.time import now_utc
from kospi_watcher.infrastructure.marketdata import get_market_data_provider


class InstrumentAnalysisService:
    def __init__(self, prediction_service: PredictionService | None = None) -> None:
        self._pred = prediction_service or PredictionService()

    async def build(self, session: AsyncSession) -> InstrumentAnalysisReport:
        row = await repositories.get_latest_prediction(session)
        if row is not None:
            pred = MarketPrediction.model_validate(row.payload)
        else:  # no stored prediction yet — generate a fresh house view (not saved)
            pred = await self._pred.generate(("069500", "114800"))

        symbols = [inst.symbol for inst in PREDICTION_UNIVERSE]
        quotes = await get_market_data_provider().get_quotes(symbols)
        prices: dict[str, tuple[Decimal | None, str]] = {
            sym: (q.price, q.source) for sym, q in quotes.items()
        }
        return build_report(
            direction=pred.direction,
            confidence=pred.confidence,
            regime=pred.regime,
            generated_by=pred.generated_by,
            prices=prices,
            as_of=now_utc(),
            monetary_policy=pred.monetary_policy,
            trend_signal=pred.trend_signal,
        )
