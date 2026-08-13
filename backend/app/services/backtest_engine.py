"""轻量日 K 双均线回测（不依赖 vnpy）。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bars import DbBarData
from app.services.watchlist_repo import resolve_symbol_pair

STRATEGIES = (
    {
        "id": "double_ma",
        "name": "双均线（日 K）",
        "interval": "d",
        "description": "快线上穿慢线买入、下穿卖出；整手 100 股；仅做多",
        "implemented": True,
    },
)

PROFILES = (
    {"profile_id": "ultra_short", "name": "极致短线", "description": "打板/半路，持仓短", "fast_window": 3, "slow_window": 8, "capital": 100_000},
    {"profile_id": "short_swing", "name": "短线波段", "description": "放量突破为主", "fast_window": 5, "slow_window": 20, "capital": 100_000},
    {"profile_id": "medium_watch", "name": "中线观察", "description": "趋势跟踪辅助", "fast_window": 10, "slow_window": 30, "capital": 100_000},
    {"profile_id": "trend", "name": "趋势", "description": "均线趋势，持仓更长", "fast_window": 20, "slow_window": 60, "capital": 100_000},
)


@dataclass
class Bar:
    dt: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if window <= 0:
        return out
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out[i] = s / window
    return out


def load_daily_bars(
    db: Session,
    *,
    vt_symbol: str,
    start_date: str,
    end_date: str,
) -> list[Bar]:
    symbol, exchange = resolve_symbol_pair(vt_symbol)
    try:
        start = datetime.fromisoformat(start_date[:10])
        end = datetime.fromisoformat(end_date[:10]).replace(hour=23, minute=59, second=59)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式须为 YYYY-MM-DD") from exc

    rows = list(
        db.scalars(
            select(DbBarData)
            .where(
                DbBarData.symbol == symbol,
                DbBarData.exchange == exchange,
                DbBarData.interval == "d",
                DbBarData.datetime >= start,
                DbBarData.datetime <= end,
            )
            .order_by(DbBarData.datetime)
        )
    )
    if len(rows) < 30:
        raise HTTPException(status_code=404, detail=f"日 K 不足（{len(rows)}），请先在 Ops 补全日 K")
    return [
        Bar(
            dt=r.datetime,
            open=float(r.open_price or 0),
            high=float(r.high_price or 0),
            low=float(r.low_price or 0),
            close=float(r.close_price or 0),
            volume=float(r.volume or 0),
        )
        for r in rows
        if (r.close_price or 0) > 0
    ]


def run_double_ma(
    bars: list[Bar],
    *,
    fast_window: int = 5,
    slow_window: int = 20,
    capital: float = 100_000,
    commission_rate: float = 0.00045,
) -> dict[str, Any]:
    if fast_window >= slow_window:
        raise HTTPException(status_code=400, detail="fast_window 须小于 slow_window")
    closes = [b.close for b in bars]
    fast = _sma(closes, fast_window)
    slow = _sma(closes, slow_window)

    cash = capital
    shares = 0
    entry_price = 0.0
    trades: list[dict[str, Any]] = []
    equity: list[dict[str, Any]] = []
    peak = capital
    max_dd = 0.0
    daily_returns: list[float] = []
    prev_equity = capital

    for i, bar in enumerate(bars):
        f, s = fast[i], slow[i]
        # 信号用当日收盘，下一根开盘成交（简化：同日收盘成交）
        if f is not None and s is not None and i > 0:
            pf, ps = fast[i - 1], slow[i - 1]
            if pf is not None and ps is not None:
                # 金叉买入
                if pf <= ps and f > s and shares == 0:
                    lot_cost = bar.close * 100 * (1 + commission_rate)
                    lots = int(cash // lot_cost)
                    if lots > 0:
                        qty = lots * 100
                        cost = qty * bar.close
                        fee = cost * commission_rate
                        cash -= cost + fee
                        shares = qty
                        entry_price = bar.close
                        trades.append(
                            {
                                "datetime": bar.dt.date().isoformat(),
                                "side": "buy",
                                "price": bar.close,
                                "volume": qty,
                                "fee": round(fee, 2),
                            }
                        )
                # 死叉卖出
                elif pf >= ps and f < s and shares > 0:
                    proceeds = shares * bar.close
                    fee = proceeds * commission_rate
                    cash += proceeds - fee
                    trades.append(
                        {
                            "datetime": bar.dt.date().isoformat(),
                            "side": "sell",
                            "price": bar.close,
                            "volume": shares,
                            "fee": round(fee, 2),
                            "pnl": round((bar.close - entry_price) * shares - fee, 2),
                        }
                    )
                    shares = 0
                    entry_price = 0.0

        eq = cash + shares * bar.close
        equity.append({"datetime": bar.dt.date().isoformat(), "equity": round(eq, 2)})
        if prev_equity > 0:
            daily_returns.append((eq - prev_equity) / prev_equity)
        prev_equity = eq
        if eq > peak:
            peak = eq
        dd = (eq - peak) / peak if peak else 0.0
        if dd < max_dd:
            max_dd = dd

    # 强制平仓
    if shares > 0 and bars:
        bar = bars[-1]
        proceeds = shares * bar.close
        fee = proceeds * commission_rate
        cash += proceeds - fee
        trades.append(
            {
                "datetime": bar.dt.date().isoformat(),
                "side": "sell",
                "price": bar.close,
                "volume": shares,
                "fee": round(fee, 2),
                "pnl": round((bar.close - entry_price) * shares - fee, 2),
                "force": True,
            }
        )
        shares = 0
        eq = cash
        if equity:
            equity[-1]["equity"] = round(eq, 2)

    final = equity[-1]["equity"] if equity else capital
    total_return = (final - capital) / capital * 100.0
    # 简化年化夏普
    if len(daily_returns) > 2:
        mean = sum(daily_returns) / len(daily_returns)
        var = sum((x - mean) ** 2 for x in daily_returns) / (len(daily_returns) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        sharpe = (mean / std) * math.sqrt(252) if std > 0 else 0.0
    else:
        sharpe = 0.0

    sell_trades = [t for t in trades if t["side"] == "sell"]
    return {
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_dd * 100.0, 4),
        "sharpe_ratio": round(sharpe, 4),
        "trade_count": len(sell_trades),
        "final_equity": round(final, 2),
        "capital": capital,
        "fast_window": fast_window,
        "slow_window": slow_window,
        "bar_count": len(bars),
        "equity_curve": equity,
        "trades": trades,
        "statistics": {
            "total_return": round(total_return, 4),
            "max_drawdown": round(max_dd * 100.0, 4),
            "sharpe_ratio": round(sharpe, 4),
            "total_trade_count": len(sell_trades),
            "final_equity": round(final, 2),
        },
    }
