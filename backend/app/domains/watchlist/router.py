"""自选 / 持仓 / 信号 / 行情视图薄路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.domains.content import notify_log
from app.domains.watchlist import market_views, trading_risk
from app.domains.watchlist.positions import PositionsService
from app.domains.watchlist.schemas import (
    BarsResponse,
    FundamentalsOut,
    GroupCreate,
    GroupMemberOut,
    GroupMemberRequest,
    GroupMembersBatchOut,
    GroupMembersBatchRequest,
    GroupOut,
    GroupRename,
    GroupsReorderRequest,
    NotifyLogOut,
    PositionOut,
    PositionUpsertRequest,
    QuoteOut,
    SignalPanelMemberRequest,
    SignalPanelOut,
    SignalPanelReplaceRequest,
    StrategyBoardOut,
    TradingRiskPrefsOut,
    TradingRiskPrefsPut,
    WatchlistAddRequest,
    WatchlistItemOut,
    WatchlistReorderRequest,
)
from app.domains.watchlist.service import WatchlistService
from app.domains.watchlist.signal_panel import SignalPanelService
from app.models.user import User
from app.schemas.common import ApiResponse, OkOut
from app.services.strategy import strategy_board

router = APIRouter(tags=["watchlist"])


@router.get("/watchlist", response_model=ApiResponse[list[WatchlistItemOut]])
def get_watchlist(
    enrich: bool = Query(default=True),
    group_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[WatchlistItemOut]]:
    return ApiResponse(
        data=WatchlistService.list_items(db, str(user.id), enrich=enrich, group_id=group_id)
    )


@router.get("/watchlist/strategy-board", response_model=ApiResponse[StrategyBoardOut])
def get_strategy_board(
    config_key: str | None = Query(default=None, description="缺省读用户偏好或默认短线突破 5/10"),
    signal_mode: str = Query(
        default="heuristic_v2",
        description="heuristic_v2 | double_ma | trend_ma | medium_swing | donchian | rsi_reversal | bollinger | ma_band | atr_breakout",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[StrategyBoardOut]:
    return ApiResponse(
        data=StrategyBoardOut(
            **strategy_board.load_strategy_board(
                db, str(user.id), config_key=config_key, signal_mode=signal_mode
            )
        )
    )


@router.get("/watchlist/trading-risk", response_model=ApiResponse[TradingRiskPrefsOut])
def get_trading_risk(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[TradingRiskPrefsOut]:
    return ApiResponse(data=trading_risk.load_trading_risk_prefs(db, str(user.id)))


@router.get("/watchlist/notify-log", response_model=ApiResponse[NotifyLogOut])
def get_notify_log(
    limit: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[NotifyLogOut]:
    return ApiResponse(data=notify_log.list_notify_log(db, str(user.id), limit=limit))


@router.put("/watchlist/trading-risk", response_model=ApiResponse[TradingRiskPrefsOut])
def put_trading_risk(
    body: TradingRiskPrefsPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[TradingRiskPrefsOut]:
    prefs = trading_risk.save_trading_risk_prefs(
        db,
        str(user.id),
        body.model_dump(exclude_unset=True),
    )
    return ApiResponse(data=prefs)


@router.get("/watchlist/signal-panel", response_model=ApiResponse[SignalPanelOut])
def get_signal_panel(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SignalPanelOut]:
    return ApiResponse(data=SignalPanelService.get(db, str(user.id)))


@router.put("/watchlist/signal-panel", response_model=ApiResponse[SignalPanelOut])
def put_signal_panel(
    body: SignalPanelReplaceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SignalPanelOut]:
    return ApiResponse(data=SignalPanelService.replace(db, str(user.id), body))


@router.post("/watchlist/signal-panel/members", response_model=ApiResponse[SignalPanelOut])
def post_signal_panel_member(
    body: SignalPanelMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SignalPanelOut]:
    return ApiResponse(data=SignalPanelService.add(db, str(user.id), body))


@router.delete("/watchlist/signal-panel/members/{vt_symbol}", response_model=ApiResponse[SignalPanelOut])
def delete_signal_panel_member(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SignalPanelOut]:
    return ApiResponse(data=SignalPanelService.remove(db, str(user.id), vt_symbol))


@router.get("/watchlist/positions", response_model=ApiResponse[list[PositionOut]])
def get_positions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[PositionOut]]:
    return ApiResponse(data=PositionsService.list(db, str(user.id)))


@router.post("/watchlist/positions", response_model=ApiResponse[PositionOut])
def post_position(
    body: PositionUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PositionOut]:
    return ApiResponse(data=PositionsService.add(db, str(user.id), body))


@router.put("/watchlist/positions/{vt_symbol}", response_model=ApiResponse[PositionOut])
def put_position(
    vt_symbol: str,
    body: PositionUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PositionOut]:
    return ApiResponse(data=PositionsService.update(db, str(user.id), vt_symbol, body))


@router.delete("/watchlist/positions/{vt_symbol}", response_model=ApiResponse[OkOut])
def delete_position(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    PositionsService.delete(db, str(user.id), vt_symbol)
    return ApiResponse(data=OkOut())


@router.post("/watchlist", response_model=ApiResponse[WatchlistItemOut])
def post_watchlist(
    body: WatchlistAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[WatchlistItemOut]:
    return ApiResponse(data=WatchlistService.add_item(db, str(user.id), body))


@router.put("/watchlist/reorder", response_model=ApiResponse[list[WatchlistItemOut]])
def put_reorder(
    body: WatchlistReorderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[WatchlistItemOut]]:
    return ApiResponse(data=WatchlistService.reorder(db, str(user.id), body))


@router.get("/watchlist/groups", response_model=ApiResponse[list[GroupOut]])
def get_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[GroupOut]]:
    return ApiResponse(data=WatchlistService.list_groups(db, str(user.id)))


@router.put("/watchlist/groups/reorder", response_model=ApiResponse[list[GroupOut]])
def put_groups_reorder(
    body: GroupsReorderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[GroupOut]]:
    return ApiResponse(data=WatchlistService.reorder_groups(db, str(user.id), body))


@router.post("/watchlist/groups", response_model=ApiResponse[GroupOut])
def post_group(
    body: GroupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[GroupOut]:
    return ApiResponse(data=WatchlistService.create_group(db, str(user.id), body))


@router.patch("/watchlist/groups/{group_id}", response_model=ApiResponse[GroupOut])
def patch_group(
    group_id: str,
    body: GroupRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[GroupOut]:
    return ApiResponse(data=WatchlistService.rename_group(db, str(user.id), group_id, body))


@router.delete("/watchlist/groups/{group_id}", response_model=ApiResponse[OkOut])
def remove_group(
    group_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    WatchlistService.delete_group(db, str(user.id), group_id)
    return ApiResponse(data=OkOut())


@router.post("/watchlist/groups/{group_id}/members", response_model=ApiResponse[GroupMemberOut])
def post_group_member(
    group_id: str,
    body: GroupMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[GroupMemberOut]:
    return ApiResponse(data=WatchlistService.add_member(db, str(user.id), group_id, body))


@router.post("/watchlist/groups/{group_id}/members/batch", response_model=ApiResponse[GroupMembersBatchOut])
def post_group_members_batch(
    group_id: str,
    body: GroupMembersBatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[GroupMembersBatchOut]:
    return ApiResponse(data=WatchlistService.batch_members(db, str(user.id), group_id, body))


@router.delete("/watchlist/groups/{group_id}/members/{vt_symbol}", response_model=ApiResponse[OkOut])
def delete_group_member(
    group_id: str,
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    WatchlistService.remove_member(db, str(user.id), group_id, vt_symbol)
    return ApiResponse(data=OkOut())


@router.delete("/watchlist/{vt_symbol}", response_model=ApiResponse[OkOut])
def delete_watchlist(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    WatchlistService.remove_item(db, str(user.id), vt_symbol)
    return ApiResponse(data=OkOut())


@router.get("/quotes", response_model=ApiResponse[list[QuoteOut]])
def get_quotes(
    symbols: str = Query(description="逗号分隔 vt_symbol，如 600519.SSE,000001.SZSE"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[QuoteOut]]:
    _ = user
    return ApiResponse(data=market_views.get_quotes(db, symbols))


@router.get("/watchlist/items/{vt_symbol}/fundamentals", response_model=ApiResponse[FundamentalsOut])
def get_item_fundamentals(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FundamentalsOut]:
    _ = user
    return ApiResponse(data=market_views.get_fundamentals(db, vt_symbol))


@router.get("/bars/{vt_symbol}", response_model=ApiResponse[BarsResponse])
def get_bars(
    vt_symbol: str,
    interval: str = Query(default="d"),
    limit: int = Query(default=120, ge=1, le=2000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[BarsResponse]:
    _ = user
    return ApiResponse(data=market_views.get_bars(db, vt_symbol, interval=interval, limit=limit))
