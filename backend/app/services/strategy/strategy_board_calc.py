"""自选策略看板：日 K 加载、信号计算与持仓增强（strategy_board 拆分）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.models.bars import DbBarData
from app.services.symbols import normalize_exchange, to_vt_symbol
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
from app.services.strategy.strategy_board_config import (
    BAR_LIMIT,
    DEFAULT_DOUBLE_MA_FAST,
    DEFAULT_DOUBLE_MA_SLOW,
    SIGNAL_MODE_ATR_BREAKOUT,
    SIGNAL_MODE_BOLLINGER,
    SIGNAL_MODE_DONCHIAN,
    SIGNAL_MODE_DOUBLE_MA,
    SIGNAL_MODE_MA_BAND,
    SIGNAL_MODE_MEDIUM_SWING,
    SIGNAL_MODE_RSI_REVERSAL,
    SIGNAL_MODE_TREND_MA,
)


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
