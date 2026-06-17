"""Prediction & daily-brief endpoints.

POST /prediction/run    — run all agents, synthesize, persist, return prediction
GET  /prediction/latest — the most recent stored prediction
GET  /brief             — the latest daily brief (narrative + stances)
GET  /agents/org        — the desk hierarchy (read-only)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from kospi_watcher.agent_service.prediction import PredictionService
from kospi_watcher.api.deps import SessionDep
from kospi_watcher.api.schemas.requests import MockRunRequest
from kospi_watcher.api.schemas.responses import (
    BriefResponse,
    BriefStance,
    OrgDeskInfo,
    OrgResponse,
)
from kospi_watcher.db import repositories
from kospi_watcher.db.repositories import add_audit_log, save_prediction
from kospi_watcher.domain.agents.org import AGENT_ORG, Tier
from kospi_watcher.domain.enums import AuditAction
from kospi_watcher.domain.prediction.schemas import MarketPrediction

router = APIRouter(tags=["prediction"])
_service = PredictionService()


@router.post("/prediction/run", response_model=MarketPrediction)
async def run_prediction(req: MockRunRequest, session: SessionDep) -> MarketPrediction:
    headlines = await repositories.recent_headlines(session, limit=8)
    prediction = await _service.generate(
        tuple(req.universe) or ("069500", "114800"), news_headlines=headlines
    )
    await save_prediction(session, prediction)
    await add_audit_log(
        session,
        action=AuditAction.AGENT_RUN,
        entity_type="prediction",
        entity_id=prediction.prediction_id,
        summary=(
            f"prediction {prediction.direction.value} "
            f"({prediction.regime.value}) by {prediction.generated_by}"
        ),
        payload={"direction": prediction.direction.value, "regime": prediction.regime.value},
    )
    await session.commit()
    return prediction


@router.get("/prediction/latest", response_model=MarketPrediction)
async def latest_prediction(session: SessionDep) -> MarketPrediction:
    row = await repositories.get_latest_prediction(session)
    if row is None:
        raise HTTPException(status_code=404, detail="no prediction yet; POST /prediction/run")
    return MarketPrediction.model_validate(row.payload)


@router.get("/brief", response_model=BriefResponse)
async def daily_brief(session: SessionDep) -> BriefResponse:
    row = await repositories.get_latest_prediction(session)
    if row is None:
        raise HTTPException(status_code=404, detail="no brief yet; POST /prediction/run")
    pred = MarketPrediction.model_validate(row.payload)
    return BriefResponse(
        as_of=pred.as_of,
        subject=pred.subject,
        horizon_label=pred.horizon_label,
        generated_by=pred.generated_by,
        agent_count=pred.agent_count,
        direction=pred.direction.value,
        confidence=pred.confidence,
        regime=pred.regime.value,
        headline=pred.headline,
        brief=pred.brief,
        news_refs=pred.news_refs,
        stances=[
            BriefStance(
                symbol=s.symbol,
                name=s.name,
                kind=s.kind.value,
                label=s.label.value,
                risk_note=s.risk_note,
            )
            for s in pred.instrument_stances
        ],
    )


@router.get("/agents/org", response_model=OrgResponse)
async def agents_org() -> OrgResponse:
    return OrgResponse(
        desks=[
            OrgDeskInfo(
                key=d.key.value,
                title=d.title_ko,
                tier=d.tier.value,
                weight=d.weight,
                lead=d.lead,
                members=list(d.members),
            )
            for d in AGENT_ORG
        ],
        tiers=[t.value for t in Tier],
        agent_count=sum(len(d.members) for d in AGENT_ORG),
    )
