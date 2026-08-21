"""自选策略看盘：看板请求时实时按日 K 计算信号（不再依赖预热缓存）。

config 解析见 strategy_board_config，K 线/信号计算见 strategy_board_calc。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domains.market.quotes import get_quote_store
from app.domains.watchlist import positions_repo
from app.domains.watchlist import repository as repo
from app.domains.watchlist import signal_panel_repo
from app.domains.watchlist.trading_risk import (
    compute_actual_position_pct,
    load_trading_risk_prefs,
)
from app.services.symbols import to_tf_symbol, to_vt_symbol
from app.services.strategy.strategy_board_calc import (
    _compute_snapshot,
    _load_daily_bars_map,
    _pack_signal_row,
    _parse_payload,
    _safe_float,
    _signal_label,
    _t1_locked,
    enrich_position_risk,
)
from app.services.strategy.strategy_board_config import (
    ALL_SIGNAL_MODES,
    BAR_LIMIT,
    DEFAULT_CONFIG_KEY,
    DEFAULT_DOUBLE_MA_FAST,
    DEFAULT_DOUBLE_MA_SLOW,
    SIGNAL_MODE_ATR_BREAKOUT,
    SIGNAL_MODE_BOLLINGER,
    SIGNAL_MODE_DONCHIAN,
    SIGNAL_MODE_DOUBLE_MA,
    SIGNAL_MODE_HEURISTIC,
    SIGNAL_MODE_MA_BAND,
    SIGNAL_MODE_MEDIUM_SWING,
    SIGNAL_MODE_RSI_REVERSAL,
    SIGNAL_MODE_TREND_MA,
    bars_limit_for,
    resolve_board_config_key,
    resolve_config_key,
)


def load_strategy_board(
    db: Session,
    user_id: str,
    *,
    config_key: str | None = None,
    signal_mode: str = SIGNAL_MODE_HEURISTIC,
) -> dict[str, Any]:
    mode = (signal_mode or SIGNAL_MODE_HEURISTIC).strip() or SIGNAL_MODE_HEURISTIC
    if mode not in ALL_SIGNAL_MODES:
        mode = SIGNAL_MODE_HEURISTIC
    ck = resolve_board_config_key(db, user_id, signal_mode=mode, override=config_key)
    items = repo.WatchlistItemRepository(db, user_id).list_items()
    name_by_vt = {to_vt_symbol(i.symbol, i.exchange): (i.name or "") for i in items}
    watchlist_vts = list(name_by_vt.keys())
    panel_symbols = signal_panel_repo.SignalPanelRepository(db, user_id).load_symbols()
    # 名单优先；空则回退自选
    universe = panel_symbols if panel_symbols else watchlist_vts

    # 行情（自选 + 名单并集）
    quote_vts = list(dict.fromkeys([*watchlist_vts, *panel_symbols]))
    quote_by_vt: dict[str, Any] = {}
    store = get_quote_store()
    if store.available() and quote_vts:
        tfs = []
        tf_to_vt: dict[str, str] = {}
        for vt in quote_vts:
            if "." not in vt:
                continue
            code, exch = vt.rsplit(".", 1)
            tf = to_tf_symbol(code, exch)
            tfs.append(tf)
            tf_to_vt[tf] = vt
        for quote in store.get_quotes(tfs):
            mapped_vt = tf_to_vt.get(quote.symbol)
            if mapped_vt:
                quote_by_vt[mapped_vt] = quote
                if not name_by_vt.get(mapped_vt) and quote.name:
                    name_by_vt[mapped_vt] = quote.name

    # 实时计算：批量加载日 K → 按 mode 计算信号
    symbols: list[tuple[str, str]] = []
    for vt in universe:
        if "." not in vt:
            continue
        code, exch = vt.rsplit(".", 1)
        symbols.append((code, exch))
    bars = _load_daily_bars_map(db, symbols, limit=bars_limit_for(mode, ck))
    snap_by_vt: dict[str, dict[str, Any]] = {}
    for vt in universe:
        data = bars.get(vt)
        if not data:
            continue
        snap = _compute_snapshot(
            mode,
            highs=data["highs"],
            lows=data["lows"],
            closes=data["closes"],
            volumes=data["volumes"],
            vt_symbol=vt,
            as_of=data["as_of"],
            config_key=ck,
        )
        if snap:
            snap_by_vt[vt] = snap

    signals: list[dict[str, Any]] = []
    for vt in universe:
        snap = snap_by_vt.get(vt)
        if not snap:
            continue
        q = quote_by_vt.get(vt)
        signals.append(
            _pack_signal_row(
                vt,
                snap,
                name=name_by_vt.get(vt, ""),
                last_price=getattr(q, "last_price", None) if q else None,
                change_pct=getattr(q, "change_pct", None) if q else None,
            )
        )

    # 有名单时：按名单顺序；否则按强度
    if panel_symbols:
        order = {vt: i for i, vt in enumerate(panel_symbols)}
        signals.sort(key=lambda r: order.get(str(r.get("vt_symbol")), 999))
    else:
        signals.sort(key=lambda r: float(r.get("strength") or -1), reverse=True)

    as_of = ""
    for s in signals:
        if s.get("bar_as_of"):
            as_of = str(s["bar_as_of"])
            break

    prefs = load_trading_risk_prefs(db, user_id)

    # 持仓记账
    pos_rows = positions_repo.PositionRepository(db, user_id).list_positions()

    positions: list[dict[str, Any]] = []
    for row in pos_rows:
        symbol = str(row.symbol)
        exchange = str(row.exchange)
        vt = to_vt_symbol(symbol, exchange)
        cost = float(row.cost_price or 0)
        volume = int(row.volume or 0)
        buy_date = str(row.buy_date or "")[:10]
        q = quote_by_vt.get(vt)
        last = getattr(q, "last_price", None) if q else None
        if last is None or last <= 0:
            last = None
        market_value = pnl = pnl_pct = None
        if last is not None and last > 0 and cost > 0 and volume > 0:
            market_value = round(last * volume, 2)
            pnl = round(market_value - cost * volume, 2)
            pnl_pct = round((last - cost) / cost * 100, 2)

        exit_snap = snap_by_vt.get(vt)
        exit_kind = str((exit_snap or {}).get("signal") or "na")
        pos_change_pct: float | None = None
        pos_volume_ratio: float | None = None
        if q is not None:
            pos_change_pct = float(getattr(q, "change_pct", 0) or 0)
            pos_volume_ratio = float(getattr(q, "volume_ratio", 0) or 0)
        positions.append(
            enrich_position_risk(
                {
                    "vt_symbol": vt,
                    "name": name_by_vt.get(vt) or (getattr(q, "name", "") if q else ""),
                    "cost_price": cost,
                    "volume": volume,
                    "buy_date": buy_date,
                    "notes": str(row.notes or ""),
                    "source": str(row.source or "manual"),
                    "last_price": last,
                    "market_value": market_value,
                    "unrealized_pnl": pnl,
                    "unrealized_pnl_pct": pnl_pct,
                    "t1_locked": _t1_locked(buy_date),
                    "exit_signal": exit_kind,
                    "exit_signal_label": _signal_label(exit_kind),
                    "ref_sell_price": _safe_float((exit_snap or {}).get("ref_sell_price")),
                    "reason_summary": str((exit_snap or {}).get("reason_summary") or ""),
                },
                change_pct=pos_change_pct,
                volume_ratio=pos_volume_ratio,
            )
        )

    total_mv = sum(float(p["market_value"] or 0) for p in positions)
    risk_summary = {
        "total_capital": prefs.total_capital,
        "actual_position_pct": compute_actual_position_pct(total_mv, prefs.total_capital),
    }

    mode_note = _mode_note(mode)
    note = ""
    if panel_symbols and not signals:
        note = (
            f"信号名单 {len(panel_symbols)} 只，暂无信号"
            "（日 K 不足或数据未补齐，可 Ops 跑补全日 K）。"
        )
    elif not signals and not positions:
        note = (
            "暂无信号。看板实时按日 K 计算；请先维护信号名单与持仓记账，"
            "并确认日 K 已补全（Ops 补全日 K）。"
        )
    elif not signals:
        note = "持仓来自记账表；当前标的日 K 不足，无法计算信号（可 Ops 跑补全日 K）。"
    note = f"{mode_note} {note}".strip() if note else mode_note

    return {
        "config_key": ck,
        "signal_mode": mode,
        "as_of": as_of or None,
        "source": "live",
        "note": note,
        "panel_symbols": panel_symbols,
        "signals": signals,
        "positions": positions,
        "risk_summary": risk_summary,
    }


def _mode_note(mode: str) -> str:
    if mode == SIGNAL_MODE_DOUBLE_MA:
        return "模式：回测双均线（当日交叉，规则对齐 /backtest double_ma）。"
    if mode == SIGNAL_MODE_TREND_MA:
        return "模式：趋势均线（入场对齐 CTA trend_ma；卖点不含追踪止损）。"
    if mode == SIGNAL_MODE_MEDIUM_SWING:
        return "模式：中线波段（MACD 金叉/死叉+站上/跌破 60 日线，对齐 /backtest medium_swing）。"
    if mode == SIGNAL_MODE_DONCHIAN:
        return "模式：唐奇安通道突破（突破 N 日新高买 / 跌破 M 日新低卖，对齐 CTA donchian）。"
    if mode == SIGNAL_MODE_RSI_REVERSAL:
        return "模式：RSI 超卖反转（自超卖回升买 / 自超买回落卖，对齐 CTA rsi_reversal）。"
    if mode == SIGNAL_MODE_BOLLINGER:
        return "模式：布林带回归（触及下轨买 / 触及上轨卖，对齐 CTA bollinger）。"
    if mode == SIGNAL_MODE_MA_BAND:
        return "模式：均线多头排列（多头形成买 / 破坏或破 20 日线卖，对齐 CTA ma_band）。"
    if mode == SIGNAL_MODE_ATR_BREAKOUT:
        return "模式：ATR 波幅突破（穿越 ATR 通道买 / 跌破卖，对齐 CTA atr_breakout）。"
    return "模式：启发式确认（交叉次日确认 N=2）。"
