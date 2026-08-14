"""轻量日 K 双均线回测（不依赖 vnpy）。STRATEGIES/PROFILES 与薄引擎仍在此；日 K 见 backtest_bars。"""

from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException

from app.services.backtest_bars import Bar, load_daily_bars

__all__ = [
    "STRATEGIES",
    "PROFILES",
    "Bar",
    "load_daily_bars",
    "run_double_ma",
    "_sma",
]

STRATEGIES = (
    {
        "id": "double_ma",
        "name": "双均线（日 K）",
        "interval": "d",
        "description": "快线上穿慢线买入、下穿卖出；整手 100 股；仅做多",
        "implemented": True,
        "engine": "vnpy",
    },
)

PROFILES = (
    {"profile_id": "ultra_short", "name": "极致短线", "description": "打板/半路，持仓短", "fast_window": 3, "slow_window": 8, "capital": 100_000},
    {"profile_id": "short_swing", "name": "短线波段", "description": "放量突破为主", "fast_window": 5, "slow_window": 20, "capital": 100_000},
    {"profile_id": "medium_watch", "name": "中线观察", "description": "趋势跟踪辅助", "fast_window": 10, "slow_window": 30, "capital": 100_000},
    {"profile_id": "trend", "name": "趋势", "description": "均线趋势，持仓更长", "fast_window": 20, "slow_window": 60, "capital": 100_000},
)


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
        if f is not None and s is not None and i > 0:
            pf, ps = fast[i - 1], slow[i - 1]
            if pf is not None and ps is not None:
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
