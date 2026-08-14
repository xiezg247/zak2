from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.market import (
    EmotionCycleOut,
    EmotionThresholdsOut,
    EmotionThresholdsPut,
    LimitListOut,
    MarketOverview,
    PlanDraftOut,
    PlanDraftRequest,
    RadarCardOut,
    RadarHorizonOut,
    RadarPredictOut,
    RadarResonanceOut,
    RadarResonanceWeightsOut,
    RadarResonanceWeightsPut,
    RankRow,
    SectorFlowRow,
    SectorIntradayPoint,
)
from app.services import emotion_cycle as emotion_cycle_svc
from app.services import emotion_thresholds as emotion_thresholds_svc
from app.services import market as market_svc
from app.services import plan_draft as plan_draft_svc
from app.services import radar as radar_svc
from app.services import radar_horizon as radar_horizon_svc
from app.services import radar_predict as radar_predict_svc
from app.services import radar_resonance as resonance_svc
from app.services import sector as sector_svc
from app.services.limit_list_store import list_limit_list

router = APIRouter(tags=["market"])


@router.get("/market/overview", response_model=MarketOverview)
def get_market_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MarketOverview:
    _ = user
    return market_svc.market_overview(db)


@router.get("/market/emotion-cycle", response_model=EmotionCycleOut)
def get_emotion_cycle(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmotionCycleOut:
    _ = user
    return EmotionCycleOut(**emotion_cycle_svc.build_emotion_cycle(db))


@router.get("/market/emotion-cycle/thresholds", response_model=EmotionThresholdsOut)
def get_emotion_thresholds(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmotionThresholdsOut:
    _ = user
    thresholds, is_default = emotion_thresholds_svc.load_thresholds(db)
    return EmotionThresholdsOut(
        **emotion_thresholds_svc.thresholds_to_dict(thresholds),
        is_default=is_default,
    )


@router.put("/market/emotion-cycle/thresholds", response_model=EmotionThresholdsOut)
def put_emotion_thresholds(
    body: EmotionThresholdsPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmotionThresholdsOut:
    _ = user
    patch = body.model_dump(exclude_unset=True)
    thresholds = emotion_thresholds_svc.save_thresholds(db, patch)
    return EmotionThresholdsOut(
        **emotion_thresholds_svc.thresholds_to_dict(thresholds),
        is_default=False,
    )


@router.post("/market/emotion-cycle/thresholds/reset", response_model=EmotionThresholdsOut)
def reset_emotion_thresholds(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmotionThresholdsOut:
    _ = user
    thresholds = emotion_thresholds_svc.reset_thresholds(db)
    return EmotionThresholdsOut(
        **emotion_thresholds_svc.thresholds_to_dict(thresholds),
        is_default=True,
    )


@router.get("/market/ranks", response_model=list[RankRow])
def get_market_ranks(
    field: str = Query(default="change_pct"),
    top_n: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[RankRow]:
    _ = user
    return market_svc.market_ranks(field, top_n=top_n)


@router.get("/sectors/dates", response_model=list[str])
def get_sector_dates(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    _ = user
    return sector_svc.list_trade_dates(db)


@router.get("/sectors/flow", response_model=list[SectorFlowRow])
def get_sector_flow(
    kind: str = Query(default="industry"),
    trade_date: str | None = None,
    sort: str = Query(default="net_flow_yi"),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SectorFlowRow]:
    _ = user
    return sector_svc.list_sector_flow(db, kind=kind, trade_date=trade_date, sort=sort, limit=limit)


@router.get("/sectors/flow/{sector_id}/intraday", response_model=list[SectorIntradayPoint])
def get_sector_intraday(
    sector_id: str,
    kind: str = Query(default="industry"),
    trade_date: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SectorIntradayPoint]:
    _ = user
    return sector_svc.sector_intraday(db, sector_id=sector_id, kind=kind, trade_date=trade_date)


@router.get("/radar/cards", response_model=list[RadarCardOut])
def get_radar_cards(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RadarCardOut]:
    _ = user
    return radar_svc.list_radar_cards(db)


@router.get("/radar/cards/{card_id}", response_model=RadarCardOut)
def get_radar_card(
    card_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadarCardOut:
    _ = user
    card = radar_svc.get_radar_card(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return card


@router.get("/radar/resonance/weights", response_model=RadarResonanceWeightsOut)
def get_resonance_weights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadarResonanceWeightsOut:
    merged = resonance_svc.load_user_weights(db, str(user.id))
    return RadarResonanceWeightsOut(**resonance_svc.weights_payload(merged))


@router.put("/radar/resonance/weights", response_model=RadarResonanceWeightsOut)
def put_resonance_weights(
    body: RadarResonanceWeightsPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadarResonanceWeightsOut:
    try:
        merged = resonance_svc.save_user_weights(db, str(user.id), dict(body.weights or {}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RadarResonanceWeightsOut(**resonance_svc.weights_payload(merged))


@router.get("/radar/resonance", response_model=RadarResonanceOut)
def get_radar_resonance(
    top_n: int = Query(default=20, ge=1, le=100),
    min_cards: int = Query(default=2, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadarResonanceOut:
    return resonance_svc.list_radar_resonance(
        db, user_id=str(user.id), min_cards=min_cards, top_n=top_n
    )


@router.get("/radar/horizon", response_model=RadarHorizonOut)
def get_radar_horizon(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadarHorizonOut:
    _ = user
    return radar_horizon_svc.load_horizon(db)


@router.get("/radar/predict", response_model=RadarPredictOut)
def get_radar_predict(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadarPredictOut:
    _ = user
    return radar_predict_svc.load_predict(db)


@router.post("/radar/plan-draft", response_model=PlanDraftOut)
def post_radar_plan_draft(
    body: PlanDraftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanDraftOut:
    result = plan_draft_svc.create_resonance_plan_draft(
        db,
        str(user.id),
        top_n=body.top_n,
        trade_date=body.trade_date,
    )
    return PlanDraftOut(**result)


@router.get("/market/limit-list", response_model=LimitListOut)
def get_limit_list(
    trade_date: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LimitListOut:
    _ = user
    return LimitListOut(**list_limit_list(db, trade_date))
