from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.watchlist import (
    BarsResponse,
    GroupCreate,
    GroupMemberRequest,
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
from app.services import notify_log, positions_repo, signal_panel_repo, strategy_board, trading_risk, watchlist_repo as repo
from app.services.bars import load_bars
from app.services.quotes import QuoteRow, get_quote_store
from app.services.stock_industry import enrich_rows_from_db
from app.services.symbols import normalize_exchange, to_tf_symbol, to_vt_symbol

router = APIRouter(tags=["watchlist"])


def _enrich(items: list, *, with_quotes: bool, db: Session | None = None) -> list[WatchlistItemOut]:  # type: ignore[no-untyped-def]
    quote_map: dict[str, QuoteRow] = {}
    if with_quotes and items:
        store = get_quote_store()
        if store.available():
            tfs = [to_tf_symbol(i.symbol, i.exchange) for i in items]
            for q in store.get_quotes(tfs):
                quote_map[q.symbol] = q

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
                vt_symbol=to_vt_symbol(item.symbol, item.exchange),
                tf_symbol=tf,
                last_price=q.last_price if q else None,
                change_pct=q.change_pct if q else None,
                turnover_rate=q.turnover_rate if q else None,
                volume=q.volume if q else None,
                amount=q.amount if q else None,
                volume_ratio=q.volume_ratio if q else None,
                industry=industry_by_tf.get(tf, "") if with_quotes else "",
            )
        )
    return out


@router.get("/watchlist", response_model=list[WatchlistItemOut])
def get_watchlist(
    enrich: bool = Query(default=True),
    group_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WatchlistItemOut]:
    items = repo.list_items(db, str(user.id))
    if group_id:
        members = {(m.symbol, m.exchange) for m in repo.list_group_members(db, str(user.id), group_id)}
        items = [i for i in items if (i.symbol, i.exchange) in members]
    return _enrich(items, with_quotes=enrich, db=db)


@router.get("/watchlist/strategy-board", response_model=StrategyBoardOut)
def get_strategy_board(
    config_key: str | None = Query(default=None, description="缺省读用户偏好或默认短线突破 5/10"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyBoardOut:
    return StrategyBoardOut(**strategy_board.load_strategy_board(db, str(user.id), config_key=config_key))


@router.get("/watchlist/trading-risk", response_model=TradingRiskPrefsOut)
def get_trading_risk(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TradingRiskPrefsOut:
    return TradingRiskPrefsOut(**trading_risk.load_trading_risk_prefs(db, str(user.id)))


@router.get("/watchlist/notify-log", response_model=NotifyLogOut)
def get_notify_log(
    limit: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotifyLogOut:
    return NotifyLogOut(**notify_log.list_notify_log(db, str(user.id), limit=limit))


@router.put("/watchlist/trading-risk", response_model=TradingRiskPrefsOut)
def put_trading_risk(
    body: TradingRiskPrefsPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TradingRiskPrefsOut:
    try:
        prefs = trading_risk.save_trading_risk_prefs(
            db,
            str(user.id),
            body.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TradingRiskPrefsOut(**prefs)


@router.get("/watchlist/signal-panel", response_model=SignalPanelOut)
def get_signal_panel(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignalPanelOut:
    return SignalPanelOut(**signal_panel_repo.panel_payload(db, str(user.id)))


@router.put("/watchlist/signal-panel", response_model=SignalPanelOut)
def put_signal_panel(
    body: SignalPanelReplaceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignalPanelOut:
    symbols = signal_panel_repo.save_symbols(db, str(user.id), body.symbols)
    return SignalPanelOut(
        symbols=symbols,
        max_symbols=signal_panel_repo.SIGNAL_PANEL_MAX_SYMBOLS,
        count=len(symbols),
    )


@router.post("/watchlist/signal-panel/members", response_model=SignalPanelOut)
def post_signal_panel_member(
    body: SignalPanelMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignalPanelOut:
    symbols = signal_panel_repo.add_symbol(db, str(user.id), body.symbol)
    return SignalPanelOut(
        symbols=symbols,
        max_symbols=signal_panel_repo.SIGNAL_PANEL_MAX_SYMBOLS,
        count=len(symbols),
    )


@router.delete("/watchlist/signal-panel/members/{vt_symbol}", response_model=SignalPanelOut)
def delete_signal_panel_member(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignalPanelOut:
    symbols = signal_panel_repo.remove_symbol(db, str(user.id), vt_symbol)
    return SignalPanelOut(
        symbols=symbols,
        max_symbols=signal_panel_repo.SIGNAL_PANEL_MAX_SYMBOLS,
        count=len(symbols),
    )


@router.get("/watchlist/positions", response_model=list[PositionOut])
def get_positions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PositionOut]:
    return [PositionOut(**row) for row in positions_repo.list_positions(db, str(user.id))]


@router.post("/watchlist/positions", response_model=PositionOut)
def post_position(
    body: PositionUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PositionOut:
    symbol, exchange = repo.resolve_symbol_pair(body.symbol, body.exchange)
    row = positions_repo.add_position(
        db,
        str(user.id),
        symbol=symbol,
        exchange=exchange,
        cost_price=body.cost_price,
        volume=body.volume,
        buy_date=body.buy_date,
        notes=body.notes,
        plan_pct=body.plan_pct,
    )
    return PositionOut(**row)


@router.put("/watchlist/positions/{vt_symbol}", response_model=PositionOut)
def put_position(
    vt_symbol: str,
    body: PositionUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PositionOut:
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    row = positions_repo.update_position(
        db,
        str(user.id),
        symbol=symbol,
        exchange=exchange,
        cost_price=body.cost_price,
        volume=body.volume,
        buy_date=body.buy_date,
        notes=body.notes,
        plan_pct=body.plan_pct,
    )
    return PositionOut(**row)


@router.delete("/watchlist/positions/{vt_symbol}")
def delete_position(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    if not positions_repo.delete_position(db, str(user.id), symbol=symbol, exchange=exchange):
        raise HTTPException(status_code=404, detail="持仓不存在")
    return {"ok": True}


@router.post("/watchlist", response_model=WatchlistItemOut)
def post_watchlist(
    body: WatchlistAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WatchlistItemOut:
    row = repo.add_item(db, str(user.id), raw_symbol=body.symbol, name=body.name, exchange=body.exchange)
    return _enrich([row], with_quotes=True, db=db)[0]


@router.put("/watchlist/reorder", response_model=list[WatchlistItemOut])
def put_reorder(
    body: WatchlistReorderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WatchlistItemOut]:
    rows = repo.reorder_items(db, str(user.id), body.items)
    return _enrich(rows, with_quotes=False, db=db)


@router.get("/watchlist/groups", response_model=list[GroupOut])
def get_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[GroupOut]:
    return [GroupOut(id=g.id, name=g.name, sort_order=g.sort_order) for g in repo.list_groups(db, str(user.id))]


@router.put("/watchlist/groups/reorder", response_model=list[GroupOut])
def put_groups_reorder(
    body: GroupsReorderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GroupOut]:
    rows = repo.reorder_groups(db, str(user.id), body.group_ids)
    return [GroupOut(id=g.id, name=g.name, sort_order=g.sort_order) for g in rows]


@router.post("/watchlist/groups", response_model=GroupOut)
def post_group(
    body: GroupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    g = repo.create_group(db, str(user.id), body.name)
    return GroupOut(id=g.id, name=g.name, sort_order=g.sort_order)


@router.patch("/watchlist/groups/{group_id}", response_model=GroupOut)
def patch_group(
    group_id: str,
    body: GroupRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    g = repo.rename_group(db, str(user.id), group_id, body.name)
    return GroupOut(id=g.id, name=g.name, sort_order=g.sort_order)


@router.delete("/watchlist/groups/{group_id}")
def remove_group(
    group_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not repo.delete_group(db, str(user.id), group_id):
        raise HTTPException(status_code=404, detail="分组不存在")
    return {"ok": True}


@router.post("/watchlist/groups/{group_id}/members")
def post_group_member(
    group_id: str,
    body: GroupMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = repo.add_group_member(db, str(user.id), group_id, body.symbol, body.exchange)
    return {"ok": True, "symbol": row.symbol, "exchange": row.exchange}


@router.delete("/watchlist/groups/{group_id}/members/{vt_symbol}")
def delete_group_member(
    group_id: str,
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    if not repo.remove_group_member(db, str(user.id), group_id, symbol, exchange):
        raise HTTPException(status_code=404, detail="分组成员不存在")
    return {"ok": True}


@router.delete("/watchlist/{vt_symbol}")
def delete_watchlist(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    if not repo.remove_item(db, str(user.id), symbol, exchange):
        raise HTTPException(status_code=404, detail="不在自选中")
    return {"ok": True}


@router.get("/quotes", response_model=list[QuoteOut])
def get_quotes(
    symbols: str = Query(description="逗号分隔 vt_symbol，如 600519.SSE,000001.SZSE"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuoteOut]:
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
    for symbol, exchange, tf in meta:
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
        out.append(
            QuoteOut(
                symbol=symbol,
                exchange=exchange,
                vt_symbol=to_vt_symbol(symbol, exchange),
                tf_symbol=tf,
                name=row.name,
                last_price=row.last_price,
                change_pct=row.change_pct,
                turnover_rate=row.turnover_rate,
                volume=row.volume,
                amount=row.amount,
                amplitude=row.amplitude,
                volume_ratio=row.volume_ratio,
                industry=row.industry or "",
            )
        )
    return out


@router.get("/bars/{vt_symbol}", response_model=BarsResponse)
def get_bars(
    vt_symbol: str,
    interval: str = Query(default="d"),
    limit: int = Query(default=120, ge=1, le=2000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BarsResponse:
    _ = user
    symbol, exchange = repo.resolve_symbol_pair(vt_symbol)
    return load_bars(db, symbol=symbol, exchange=exchange, interval=interval, limit=limit)
