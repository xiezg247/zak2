from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import positions as positions_repo
from app.repositories import signal_panel as signal_panel_repo
from app.repositories import watchlist as repo
from app.schemas.common import ApiResponse, OkOut
from app.schemas.watchlist import (
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
from app.services.content import notify_log
from app.services.market import fundamentals as fundamentals_svc
from app.services.market.bars import load_bars
from app.services.market.quotes import QuoteRow, get_quote_store
from app.services.market.stock_industry import enrich_rows_from_db
from app.services.market.suspend import load_suspended_vt_symbols
from app.services.plan import trading_risk
from app.services.strategy import strategy_board
from app.services.symbols import normalize_exchange, to_tf_symbol, to_vt_symbol

router = APIRouter(tags=["watchlist"])


def _opt_price(q: QuoteRow | None) -> float | None:
    if q is None or q.last_price <= 0:
        return None
    return float(q.last_price)


def _opt_field(q: QuoteRow | None, attr: str, *, positive: bool = False) -> float | None:
    """无行情或缺省 0（稀疏字段）时返回 None，避免前端展示假 0。"""
    if q is None:
        return None
    v = float(getattr(q, attr))
    if positive and v <= 0:
        return None
    return v


def _enrich(items: list[Any], *, with_quotes: bool, db: Session | None = None) -> list[WatchlistItemOut]:
    suspended = load_suspended_vt_symbols(db) if db is not None else set()
    quote_map: dict[str, QuoteRow] = {}
    if with_quotes and items:
        store = get_quote_store()
        if store.available():
            tfs = [to_tf_symbol(i.symbol, i.exchange) for i in items]
            for quote in store.get_quotes(tfs):
                quote_map[quote.symbol] = quote

    rows: list[QuoteRow] = []
    if with_quotes and items:
        for item in items:
            tf = to_tf_symbol(item.symbol, item.exchange)
            q = quote_map.get(tf)
            rows.append(
                QuoteRow(
                    symbol=tf,
                    name=(q.name if q and q.name else item.name) or "",
                    last_price=q.last_price if q else 0.0,
                    change_pct=q.change_pct if q else 0.0,
                    turnover_rate=q.turnover_rate if q else 0.0,
                    volume=q.volume if q else 0.0,
                    amount=q.amount if q else 0.0,
                    volume_ratio=q.volume_ratio if q else 0.0,
                    industry=(q.industry if q else "") or "",
                )
            )
        enrich_rows_from_db(db, rows)

    industry_by_tf = {r.symbol: r.industry for r in rows}
    out: list[WatchlistItemOut] = []
    for item in items:
        tf = to_tf_symbol(item.symbol, item.exchange)
        vt = to_vt_symbol(item.symbol, item.exchange)
        q = quote_map.get(tf)
        name = item.name
        if q is not None and q.name:
            name = q.name
        out.append(
            WatchlistItemOut(
                symbol=item.symbol,
                exchange=item.exchange,
                name=name,
                sort_order=item.sort_order,
                vt_symbol=vt,
                tf_symbol=tf,
                last_price=_opt_price(q),
                change_pct=_opt_field(q, "change_pct") if q else None,
                turnover_rate=_opt_field(q, "turnover_rate"),
                volume=_opt_field(q, "volume"),
                amount=_opt_field(q, "amount"),
                volume_ratio=_opt_field(q, "volume_ratio", positive=True),
                industry=industry_by_tf.get(tf, "") if with_quotes else "",
                suspended=vt in suspended,
            )
        )
    return out


@router.get("/watchlist", response_model=ApiResponse[list[WatchlistItemOut]])
def get_watchlist(
    enrich: bool = Query(default=True),
    group_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[WatchlistItemOut]]:
    items = repo.WatchlistItemRepository(db, str(user.id)).list_items()
    if group_id:
        members = {
            (m.symbol, m.exchange)
            for m in repo.WatchlistGroupMemberRepository(db, str(user.id)).list_group_members(group_id)
        }
        items = [i for i in items if (i.symbol, i.exchange) in members]
    return ApiResponse(data=_enrich(items, with_quotes=enrich, db=db))


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
            **strategy_board.load_strategy_board(db, str(user.id), config_key=config_key, signal_mode=signal_mode)
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
    try:
        prefs = trading_risk.save_trading_risk_prefs(
            db,
            str(user.id),
            body.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=prefs)


@router.get("/watchlist/signal-panel", response_model=ApiResponse[SignalPanelOut])
def get_signal_panel(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SignalPanelOut]:
    return ApiResponse(data=signal_panel_repo.SignalPanelRepository(db, str(user.id)).panel_payload())


@router.put("/watchlist/signal-panel", response_model=ApiResponse[SignalPanelOut])
def put_signal_panel(
    body: SignalPanelReplaceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SignalPanelOut]:
    symbols = signal_panel_repo.SignalPanelRepository(db, str(user.id)).save_symbols(body.symbols)
    return ApiResponse(
        data=SignalPanelOut(
            symbols=symbols,
            max_symbols=signal_panel_repo.SIGNAL_PANEL_MAX_SYMBOLS,
            count=len(symbols),
        )
    )


@router.post("/watchlist/signal-panel/members", response_model=ApiResponse[SignalPanelOut])
def post_signal_panel_member(
    body: SignalPanelMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SignalPanelOut]:
    symbols = signal_panel_repo.SignalPanelRepository(db, str(user.id)).add_symbol(body.symbol)
    return ApiResponse(
        data=SignalPanelOut(
            symbols=symbols,
            max_symbols=signal_panel_repo.SIGNAL_PANEL_MAX_SYMBOLS,
            count=len(symbols),
        )
    )


@router.delete("/watchlist/signal-panel/members/{vt_symbol}", response_model=ApiResponse[SignalPanelOut])
def delete_signal_panel_member(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SignalPanelOut]:
    symbols = signal_panel_repo.SignalPanelRepository(db, str(user.id)).remove_symbol(vt_symbol)
    return ApiResponse(
        data=SignalPanelOut(
            symbols=symbols,
            max_symbols=signal_panel_repo.SIGNAL_PANEL_MAX_SYMBOLS,
            count=len(symbols),
        )
    )


@router.get("/watchlist/positions", response_model=ApiResponse[list[PositionOut]])
def get_positions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[PositionOut]]:
    return ApiResponse(data=positions_repo.PositionRepository(db, str(user.id)).list_positions())


@router.post("/watchlist/positions", response_model=ApiResponse[PositionOut])
def post_position(
    body: PositionUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PositionOut]:
    symbol, exchange = repo.resolve_symbol_pair(body.symbol, body.exchange)
    row = positions_repo.PositionRepository(db, str(user.id)).add_position(
        symbol=symbol,
        exchange=exchange,
        cost_price=body.cost_price,
        volume=body.volume,
        buy_date=body.buy_date,
        notes=body.notes,
    )
    return ApiResponse(data=row)


@router.put("/watchlist/positions/{vt_symbol}", response_model=ApiResponse[PositionOut])
def put_position(
    vt_symbol: str,
    body: PositionUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PositionOut]:
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    row = positions_repo.PositionRepository(db, str(user.id)).update_position(
        symbol=symbol,
        exchange=exchange,
        cost_price=body.cost_price,
        volume=body.volume,
        buy_date=body.buy_date,
        notes=body.notes,
    )
    return ApiResponse(data=row)


@router.delete("/watchlist/positions/{vt_symbol}", response_model=ApiResponse[OkOut])
def delete_position(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    if not positions_repo.PositionRepository(db, str(user.id)).delete_position(symbol=symbol, exchange=exchange):
        raise HTTPException(status_code=404, detail="持仓不存在")
    return ApiResponse(data=OkOut())


@router.post("/watchlist", response_model=ApiResponse[WatchlistItemOut])
def post_watchlist(
    body: WatchlistAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[WatchlistItemOut]:
    row = repo.WatchlistItemRepository(db, str(user.id)).add_item(
        raw_symbol=body.symbol, name=body.name, exchange=body.exchange
    )
    return ApiResponse(data=_enrich([row], with_quotes=True, db=db)[0])


@router.put("/watchlist/reorder", response_model=ApiResponse[list[WatchlistItemOut]])
def put_reorder(
    body: WatchlistReorderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[WatchlistItemOut]]:
    rows = repo.WatchlistItemRepository(db, str(user.id)).reorder_items(body.items)
    return ApiResponse(data=_enrich(rows, with_quotes=False, db=db))


@router.get("/watchlist/groups", response_model=ApiResponse[list[GroupOut]])
def get_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[GroupOut]]:
    return ApiResponse(
        data=[
            GroupOut(id=g.id, name=g.name, sort_order=g.sort_order)
            for g in repo.WatchlistGroupRepository(db, str(user.id)).list_groups()
        ]
    )


@router.put("/watchlist/groups/reorder", response_model=ApiResponse[list[GroupOut]])
def put_groups_reorder(
    body: GroupsReorderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[GroupOut]]:
    rows = repo.WatchlistGroupRepository(db, str(user.id)).reorder_groups(body.group_ids)
    return ApiResponse(data=[GroupOut(id=g.id, name=g.name, sort_order=g.sort_order) for g in rows])


@router.post("/watchlist/groups", response_model=ApiResponse[GroupOut])
def post_group(
    body: GroupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[GroupOut]:
    g = repo.WatchlistGroupRepository(db, str(user.id)).create_group(body.name)
    return ApiResponse(data=GroupOut(id=g.id, name=g.name, sort_order=g.sort_order))


@router.patch("/watchlist/groups/{group_id}", response_model=ApiResponse[GroupOut])
def patch_group(
    group_id: str,
    body: GroupRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[GroupOut]:
    g = repo.WatchlistGroupRepository(db, str(user.id)).rename_group(group_id, body.name)
    return ApiResponse(data=GroupOut(id=g.id, name=g.name, sort_order=g.sort_order))


@router.delete("/watchlist/groups/{group_id}", response_model=ApiResponse[OkOut])
def remove_group(
    group_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    if not repo.WatchlistGroupRepository(db, str(user.id)).delete_group(group_id):
        raise HTTPException(status_code=404, detail="分组不存在")
    return ApiResponse(data=OkOut())


@router.post("/watchlist/groups/{group_id}/members", response_model=ApiResponse[GroupMemberOut])
def post_group_member(
    group_id: str,
    body: GroupMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[GroupMemberOut]:
    row = repo.WatchlistGroupMemberRepository(db, str(user.id)).add_group_member(group_id, body.symbol, body.exchange)
    return ApiResponse(data=GroupMemberOut(symbol=row.symbol, exchange=row.exchange))


@router.post("/watchlist/groups/{group_id}/members/batch", response_model=ApiResponse[GroupMembersBatchOut])
def post_group_members_batch(
    group_id: str,
    body: GroupMembersBatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[GroupMembersBatchOut]:
    raw = repo.WatchlistGroupMemberRepository(db, str(user.id)).batch_group_members(group_id, body.symbols, body.action)
    return ApiResponse(data=raw)


@router.delete("/watchlist/groups/{group_id}/members/{vt_symbol}", response_model=ApiResponse[OkOut])
def delete_group_member(
    group_id: str,
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    if not repo.WatchlistGroupMemberRepository(db, str(user.id)).remove_group_member(group_id, symbol, exchange):
        raise HTTPException(status_code=404, detail="分组成员不存在")
    return ApiResponse(data=OkOut())


@router.delete("/watchlist/{vt_symbol}", response_model=ApiResponse[OkOut])
def delete_watchlist(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    if not repo.WatchlistItemRepository(db, str(user.id)).remove_item(symbol, exchange):
        raise HTTPException(status_code=404, detail="不在自选中")
    return ApiResponse(data=OkOut())


@router.get("/quotes", response_model=ApiResponse[list[QuoteOut]])
def get_quotes(
    symbols: str = Query(description="逗号分隔 vt_symbol，如 600519.SSE,000001.SZSE"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[QuoteOut]]:
    _ = user
    store = get_quote_store()
    if not store.available():
        raise HTTPException(status_code=503, detail="Redis 不可用")
    tf_list: list[str] = []
    meta: list[tuple[str, str, str]] = []
    for raw in symbols.split(","):
        raw = raw.strip()
        if not raw:
            continue
        symbol, exchange = repo.resolve_symbol_pair(raw)
        tf = to_tf_symbol(symbol, exchange)
        tf_list.append(tf)
        meta.append((symbol, normalize_exchange(exchange), tf))
    quotes = {q.symbol: q for q in store.get_quotes(tf_list)}
    rows: list[QuoteRow] = []
    for _, _, tf in meta:
        q = quotes.get(tf)
        rows.append(
            QuoteRow(
                symbol=tf,
                name=q.name if q else "",
                last_price=q.last_price if q else 0.0,
                change_pct=q.change_pct if q else 0.0,
                turnover_rate=q.turnover_rate if q else 0.0,
                volume=q.volume if q else 0.0,
                amount=q.amount if q else 0.0,
                amplitude=q.amplitude if q else 0.0,
                volume_ratio=q.volume_ratio if q else 0.0,
                industry=(q.industry if q else "") or "",
            )
        )
    enrich_rows_from_db(db, rows)
    out: list[QuoteOut] = []
    for (symbol, exchange, tf), row in zip(meta, rows, strict=True):
        q = quotes.get(tf)
        out.append(
            QuoteOut(
                symbol=symbol,
                exchange=exchange,
                vt_symbol=to_vt_symbol(symbol, exchange),
                tf_symbol=tf,
                name=row.name,
                last_price=_opt_price(q),
                change_pct=_opt_field(q, "change_pct") if q else None,
                turnover_rate=_opt_field(q, "turnover_rate"),
                volume=_opt_field(q, "volume"),
                amount=_opt_field(q, "amount"),
                amplitude=_opt_field(q, "amplitude"),
                volume_ratio=_opt_field(q, "volume_ratio", positive=True),
                industry=row.industry or "",
            )
        )
    return ApiResponse(data=out)


@router.get("/watchlist/items/{vt_symbol}/fundamentals", response_model=ApiResponse[FundamentalsOut])
def get_item_fundamentals(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FundamentalsOut]:
    _ = user
    return ApiResponse(data=fundamentals_svc.get_fundamentals(db, vt_symbol))


@router.get("/bars/{vt_symbol}", response_model=ApiResponse[BarsResponse])
def get_bars(
    vt_symbol: str,
    interval: str = Query(default="d"),
    limit: int = Query(default=120, ge=1, le=2000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[BarsResponse]:
    _ = user
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    return ApiResponse(data=load_bars(db, symbol=symbol, exchange=exchange, interval=interval, limit=limit))
