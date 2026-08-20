"""自选策略看盘：看板请求时实时按日 K 计算信号（不再依赖预热缓存）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.models.bars import DbBarData
from app.repositories import positions as positions_repo
from app.repositories import signal_panel as signal_panel_repo
from app.repositories import watchlist as repo
from app.services.market.quotes import get_quote_store
from app.services.plan.trading_risk import (
    compute_actual_position_pct,
    load_trading_risk_prefs,
)
from app.services.strategy.position_risk_tags import compute_position_risk_tags, primary_risk_tag
from app.services.strategy.strategy_signal_extra import (
    compute_atr_breakout_signal,
    compute_bollinger_signal,
    compute_donchian_signal,
    compute_ma_band_signal,
    compute_rsi_reversal_signal,
)
from app.services.strategy.strategy_signal_ma import (
    compute_double_ma_signal,
    compute_ma_signal,
    compute_medium_swing_signal,
    compute_trend_ma_signal,
    parse_config_key,
)
from app.services.symbols import normalize_exchange, to_tf_symbol, to_vt_symbol

DEFAULT_CONFIG_KEY = "AshareShortBreakoutStrategy:5:10"
SIGNAL_MODE_HEURISTIC = "heuristic_v2"
SIGNAL_MODE_DOUBLE_MA = "double_ma"
SIGNAL_MODE_TREND_MA = "trend_ma"
SIGNAL_MODE_MEDIUM_SWING = "medium_swing"
SIGNAL_MODE_DONCHIAN = "donchian"
SIGNAL_MODE_RSI_REVERSAL = "rsi_reversal"
SIGNAL_MODE_BOLLINGER = "bollinger"
SIGNAL_MODE_MA_BAND = "ma_band"
SIGNAL_MODE_ATR_BREAKOUT = "atr_breakout"
ALL_SIGNAL_MODES = frozenset(
    {
        SIGNAL_MODE_HEURISTIC,
        SIGNAL_MODE_DOUBLE_MA,
        SIGNAL_MODE_TREND_MA,
        SIGNAL_MODE_MEDIUM_SWING,
        SIGNAL_MODE_DONCHIAN,
        SIGNAL_MODE_RSI_REVERSAL,
        SIGNAL_MODE_BOLLINGER,
        SIGNAL_MODE_MA_BAND,
        SIGNAL_MODE_ATR_BREAKOUT,
    }
)
DEFAULT_DOUBLE_MA_FAST = 5
DEFAULT_DOUBLE_MA_SLOW = 20
BAR_LIMIT = 120


def bars_limit_for(mode: str, config_key: str) -> int:
    """按模式决定日 K 取数上限。

    heuristic/double_ma 的 slow 可被用户配到 120（见 _pref_fast_slow），
    计算需要 slow + 确认棒；其余策略窗口 ≤62 根，120 根足够。
    """
    if mode in {SIGNAL_MODE_HEURISTIC, SIGNAL_MODE_DOUBLE_MA}:
        fast, slow = parse_config_key(config_key) or (DEFAULT_DOUBLE_MA_FAST, DEFAULT_DOUBLE_MA_SLOW)
        return max(BAR_LIMIT, slow + 2)
    return BAR_LIMIT


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_payload(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    # Redis envelope
    inner = data.get("payload")
    if isinstance(inner, str) and inner.strip().startswith("{"):
        try:
            snap = json.loads(inner)
            if isinstance(snap, dict):
                snap["_bar_as_of"] = str(data.get("bar_as_of") or snap.get("as_of") or "")
                snap["_updated_at"] = str(data.get("updated_at") or "")
                return snap
        except (json.JSONDecodeError, TypeError):
            return None
    if "signal" in data or "vt_symbol" in data:
        return data
    return None


def resolve_config_key(db: Session, user_id: str, override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    row = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE user_id = CAST(:uid AS uuid)
              AND namespace = 'watchlist' AND key = 'signal_config'
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).scalar()
    if isinstance(row, dict):
        cls = str(row.get("class_name") or "AshareShortBreakoutStrategy").strip()
        try:
            fast = max(2, min(int(row.get("fast_window") or 5), 60))
            slow = max(fast + 1, min(int(row.get("slow_window") or 10), 120))
        except (TypeError, ValueError):
            return DEFAULT_CONFIG_KEY
        return f"{cls}:{fast}:{slow}"
    return DEFAULT_CONFIG_KEY


def double_ma_config_key(fast: int, slow: int) -> str:
    return f"double_ma:{int(fast)}:{int(slow)}"


def trend_ma_config_key() -> str:
    from app.services.strategy.strategy_signal_ma import TREND_MA_FAST, TREND_MA_SLOW

    return f"trend_ma:{TREND_MA_FAST}:{TREND_MA_SLOW}"


def medium_swing_config_key() -> str:
    from app.services.strategy.strategy_signal_ma import (
        MEDIUM_SWING_FAST,
        MEDIUM_SWING_SLOW,
    )

    return f"medium_swing:{MEDIUM_SWING_FAST}:{MEDIUM_SWING_SLOW}"


def donchian_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import DONCHIAN_ENTRY, DONCHIAN_EXIT

    return f"donchian:{DONCHIAN_ENTRY}:{DONCHIAN_EXIT}"


def rsi_reversal_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import (
        RSI_OVERBOUGHT,
        RSI_OVERSOLD,
        RSI_PERIOD,
    )

    return f"rsi_reversal:{RSI_PERIOD}:{RSI_OVERSOLD}:{RSI_OVERBOUGHT}"


def bollinger_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import BOLL_DEV, BOLL_PERIOD

    return f"bollinger:{BOLL_PERIOD}:{BOLL_DEV}"


def ma_band_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import (
        MA_BAND_FAST,
        MA_BAND_LONG,
        MA_BAND_MID,
        MA_BAND_SLOW,
    )

    return f"ma_band:{MA_BAND_FAST}:{MA_BAND_MID}:{MA_BAND_SLOW}:{MA_BAND_LONG}"


def atr_breakout_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import (
        ATR_CHANNEL_PERIOD,
        ATR_MULT,
        ATR_PERIOD,
    )

    return f"atr_breakout:{ATR_CHANNEL_PERIOD}:{ATR_PERIOD}:{ATR_MULT}"


def _pref_fast_slow(db: Session, user_id: str) -> tuple[int, int]:
    row = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE user_id = CAST(:uid AS uuid)
              AND namespace = 'watchlist' AND key = 'signal_config'
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).scalar()
    if isinstance(row, dict):
        try:
            fast = max(2, min(int(row.get("fast_window") or DEFAULT_DOUBLE_MA_FAST), 60))
            slow = max(
                fast + 1,
                min(int(row.get("slow_window") or DEFAULT_DOUBLE_MA_SLOW), 120),
            )
            return fast, slow
        except (TypeError, ValueError):
            pass
    return DEFAULT_DOUBLE_MA_FAST, DEFAULT_DOUBLE_MA_SLOW


def resolve_board_config_key(
    db: Session,
    user_id: str,
    *,
    signal_mode: str = SIGNAL_MODE_HEURISTIC,
    override: str | None = None,
) -> str:
    mode = (signal_mode or SIGNAL_MODE_HEURISTIC).strip() or SIGNAL_MODE_HEURISTIC
    if override and override.strip():
        return override.strip()
    if mode == SIGNAL_MODE_DOUBLE_MA:
        fast, slow = _pref_fast_slow(db, user_id)
        return double_ma_config_key(fast, slow)
    if mode == SIGNAL_MODE_TREND_MA:
        return trend_ma_config_key()
    if mode == SIGNAL_MODE_MEDIUM_SWING:
        return medium_swing_config_key()
    if mode == SIGNAL_MODE_DONCHIAN:
        return donchian_config_key()
    if mode == SIGNAL_MODE_RSI_REVERSAL:
        return rsi_reversal_config_key()
    if mode == SIGNAL_MODE_BOLLINGER:
        return bollinger_config_key()
    if mode == SIGNAL_MODE_MA_BAND:
        return ma_band_config_key()
    if mode == SIGNAL_MODE_ATR_BREAKOUT:
        return atr_breakout_config_key()
    return resolve_config_key(db, user_id, None)


def _load_daily_bars_map(
    db: Session,
    symbols: list[tuple[str, str]],
    limit: int = BAR_LIMIT,
) -> dict[str, dict[str, Any]]:
    """批量加载日 K：返回 {vt_symbol: {highs, lows, closes, volumes, as_of}}。"""
    if not symbols:
        return {}
    conds = [
        and_(
            DbBarData.symbol == symbol,
            DbBarData.exchange == normalize_exchange(exchange),
        )
        for symbol, exchange in symbols
    ]
    rows = db.execute(
        select(DbBarData)
        .where(DbBarData.interval == "d", or_(*conds))
        .order_by(DbBarData.symbol, DbBarData.exchange, DbBarData.datetime.desc())
    ).scalars()
    grouped: dict[tuple[str, str], list[DbBarData]] = {}
    for row in rows:
        grouped.setdefault((row.symbol, row.exchange), []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for (symbol, exchange), bars in grouped.items():
        bars = bars[:limit]
        bars.reverse()
        vt = to_vt_symbol(symbol, exchange)
        out[vt] = {
            "highs": [float(b.high_price or 0) for b in bars],
            "lows": [float(b.low_price or 0) for b in bars],
            "closes": [float(b.close_price or 0) for b in bars],
            "volumes": [float(b.volume or 0) for b in bars],
            "as_of": bars[-1].datetime.date().isoformat(),
        }
    return out


def _compute_snapshot(
    mode: str,
    *,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    vt_symbol: str,
    as_of: str,
    config_key: str,
) -> dict[str, Any] | None:
    """按 mode 分派信号计算，返回与策略回测对齐的 snapshot。"""
    if mode == SIGNAL_MODE_DOUBLE_MA:
        fast, slow = parse_config_key(config_key) or (DEFAULT_DOUBLE_MA_FAST, DEFAULT_DOUBLE_MA_SLOW)
        return compute_double_ma_signal(
            closes, volumes=volumes, fast=fast, slow=slow, vt_symbol=vt_symbol, as_of=as_of
        )
    if mode == SIGNAL_MODE_TREND_MA:
        return compute_trend_ma_signal(
            highs, lows, closes, volumes=volumes, vt_symbol=vt_symbol, as_of=as_of
        )
    if mode == SIGNAL_MODE_MEDIUM_SWING:
        return compute_medium_swing_signal(
            closes, volumes=volumes, vt_symbol=vt_symbol, as_of=as_of
        )
    if mode == SIGNAL_MODE_DONCHIAN:
        return compute_donchian_signal(
            highs, lows, closes, volumes=volumes, vt_symbol=vt_symbol, as_of=as_of
        )
    if mode == SIGNAL_MODE_RSI_REVERSAL:
        return compute_rsi_reversal_signal(
            closes, volumes=volumes, vt_symbol=vt_symbol, as_of=as_of
        )
    if mode == SIGNAL_MODE_BOLLINGER:
        return compute_bollinger_signal(
            closes, volumes=volumes, vt_symbol=vt_symbol, as_of=as_of
        )
    if mode == SIGNAL_MODE_MA_BAND:
        return compute_ma_band_signal(
            closes, volumes=volumes, vt_symbol=vt_symbol, as_of=as_of
        )
    if mode == SIGNAL_MODE_ATR_BREAKOUT:
        return compute_atr_breakout_signal(
            highs, lows, closes, volumes=volumes, vt_symbol=vt_symbol, as_of=as_of
        )
    fast, slow = parse_config_key(config_key) or (DEFAULT_DOUBLE_MA_FAST, DEFAULT_DOUBLE_MA_SLOW)
    return compute_ma_signal(
        closes, volumes=volumes, fast=fast, slow=slow, vt_symbol=vt_symbol, as_of=as_of
    )


def _t1_locked(buy_date: str) -> bool:
    text_v = (buy_date or "").strip()[:10]
    if not text_v:
        return False
    try:
        parsed = datetime.strptime(text_v, "%Y-%m-%d").date()
    except ValueError:
        return False
    return parsed >= china_today()


def _signal_label(kind: str) -> str:
    return {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}.get(kind, kind or "—")


def enrich_position_risk(
    row: dict[str, Any],
    *,
    change_pct: float | None,
    volume_ratio: float | None,
) -> dict[str, Any]:
    tags = compute_position_risk_tags(
        exit_signal=str(row.get("exit_signal") or ""),
        unrealized_pnl_pct=row.get("unrealized_pnl_pct"),
        change_pct=change_pct,
        volume_ratio=volume_ratio,
    )
    row["risk_tags"] = tags
    row["risk_primary"] = primary_risk_tag(tags)
    return row


def _pack_signal_row(
    vt_symbol: str,
    snap: dict[str, Any],
    *,
    name: str = "",
    last_price: float | None = None,
    change_pct: float | None = None,
) -> dict[str, Any]:
    kind = str(snap.get("signal") or "na")
    price = last_price if last_price is not None else _safe_float(snap.get("last_close"))
    return {
        "vt_symbol": vt_symbol,
        "name": name or str(snap.get("name") or ""),
        "last_price": price,
        "change_pct": change_pct,
        "signal": kind,
        "signal_label": str(snap.get("signal_label") or _signal_label(kind)),
        "signal_date": str(snap.get("signal_date") or "")[:10] or None,
        "strength": _safe_float(snap.get("strength")),
        "strength_tier": str(snap.get("strength_tier") or "") or None,
        "strength_tier_label": str(snap.get("strength_tier_label") or "") or None,
        "reason_summary": str(snap.get("reason_summary") or ""),
        "ref_buy_price": _safe_float(snap.get("ref_buy_price")),
        "ref_sell_price": _safe_float(snap.get("ref_sell_price")),
        "ma_gap_pct": _safe_float(snap.get("ma_gap_pct")),
        "volume_ratio_5d": _safe_float(snap.get("volume_ratio_5d")),
        "bar_as_of": str(snap.get("_bar_as_of") or snap.get("as_of") or "")[:10] or None,
        "updated_at": str(snap.get("_updated_at") or "") or None,
    }


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
