"""将 vnpy 统计结果映射为 zak2 落库结构（不硬依赖 vnpy）。"""

from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        text = str(value).replace("%", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return None


def map_vnpy_statistics(
    stats: dict[str, Any],
    *,
    trades: list[dict[str, Any]] | None = None,
    daily_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """统一为 UI 可用的百分比数值 + equity_curve / trades。"""
    trades = list(trades or [])
    daily_rows = list(daily_rows or [])

    total_return = _to_float(stats.get("total_return"))
    max_drawdown = _to_float(stats.get("max_drawdown"))
    sharpe_ratio = _to_float(stats.get("sharpe_ratio"))
    trade_count_raw = stats.get("total_trade_count", stats.get("trade_count"))
    try:
        trade_count = int(trade_count_raw) if trade_count_raw is not None else None
    except (TypeError, ValueError):
        trade_count = None

    equity_curve: list[dict[str, Any]] = []
    for row in daily_rows:
        dt = row.get("date") or row.get("datetime")
        bal = row.get("balance") or row.get("equity")
        if dt is None or bal is None:
            continue
        equity_curve.append({"datetime": str(dt)[:10], "equity": float(bal)})

    statistics = dict(stats)
    # 规范化常用键，便于前端厚指标读取
    for key in (
        "annual_return",
        "return_std",
        "sharpe_ratio",
        "win_rate",
        "profit_loss_ratio",
        "max_drawdown",
        "total_return",
    ):
        if key in statistics:
            parsed = _to_float(statistics[key])
            if parsed is not None:
                statistics[key] = parsed

    return {
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "trade_count": trade_count,
        "statistics": statistics,
        "equity_curve": equity_curve,
        "trades": trades,
    }
