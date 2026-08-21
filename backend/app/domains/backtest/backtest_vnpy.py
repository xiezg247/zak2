"""vnpy CTA 回测编排：PG K 线注入 history_data，不调用 load_data()。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from vnpy.trader.constant import Direction, Exchange, Interval
from vnpy.trader.object import BarData
from vnpy_ctastrategy.backtesting import BacktestingEngine, DailyResult
from vnpy_ctastrategy.base import BacktestingMode

from app.domains.backtest.backtest_map import map_vnpy_statistics
from app.strategies.cta.registry import get_strategy_class


def vnpy_interval(interval: str) -> Interval:
    key = (interval or "d").strip().lower()
    if key == "1m":
        return Interval.MINUTE
    if key == "d":
        return Interval.DAILY
    raise ValueError(f"不支持的周期：{interval}")


class AShareDailyResult(DailyResult):
    """卖出成交额外计提印花税。"""

    def calculate_pnl(
        self,
        pre_close: float,
        start_pos: float,
        size: float,
        rate: float,
        slippage: float,
        stamp_duty: float = 0.0,
    ) -> None:
        super().calculate_pnl(pre_close, start_pos, size, rate, slippage)
        extra = 0.0
        for trade in self.trades:
            if trade.direction == Direction.SHORT:
                extra += trade.volume * size * trade.price * stamp_duty
        if extra:
            self.commission += extra
            self.net_pnl -= extra


class AShareBacktestingEngine(BacktestingEngine):
    """支持 stamp_duty 的回测引擎。"""

    def __init__(self) -> None:
        super().__init__()
        self.stamp_duty: float = 0.0

    def update_daily_close(self, price: float) -> None:
        d = self.datetime.date()
        daily_result = self.daily_results.get(d, None)
        if daily_result:
            daily_result.close_price = price
        else:
            self.daily_results[d] = AShareDailyResult(d, price)

    def calculate_result(self) -> Any:
        self.output("开始计算逐日盯市盈亏")
        if not self.trades:
            self.output("回测成交记录为空")

        for trade in self.trades.values():
            if not trade.datetime:
                continue
            d = trade.datetime.date()
            daily_result = self.daily_results[d]
            daily_result.add_trade(trade)

        pre_close = 0.0
        start_pos = 0.0
        for daily_result in self.daily_results.values():
            if isinstance(daily_result, AShareDailyResult):
                daily_result.calculate_pnl(pre_close, start_pos, self.size, self.rate, self.slippage, self.stamp_duty)
            else:
                daily_result.calculate_pnl(pre_close, start_pos, self.size, self.rate, self.slippage)
            pre_close = daily_result.close_price
            start_pos = daily_result.end_pos

        from collections import defaultdict

        from pandas import DataFrame

        results: defaultdict = defaultdict(list)
        for daily_result in self.daily_results.values():
            for key, value in daily_result.__dict__.items():
                results[key].append(value)

        if results:
            self.daily_df = DataFrame.from_dict(results).set_index("date")

        self.output("逐日盯市盈亏计算完成")
        return self.daily_df


def _parse_exchange(vt_symbol: str) -> tuple[str, Exchange]:
    if "." not in vt_symbol:
        raise ValueError(f"无效 vt_symbol：{vt_symbol}")
    symbol, suffix = vt_symbol.rsplit(".", 1)
    try:
        exchange = Exchange(suffix)
    except ValueError as exc:
        raise ValueError(f"未知交易所：{suffix}") from exc
    return symbol, exchange


def records_to_bars(
    records: list[dict],
    *,
    vt_symbol: str,
    interval: str = "d",
) -> list[BarData]:
    symbol, exchange = _parse_exchange(vt_symbol)
    iv = vnpy_interval(interval)
    bars: list[BarData] = []
    for row in records:
        dt = row["datetime"]
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                interval=iv,
                volume=float(row.get("volume") or 0),
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                close_price=float(row["close"]),
                open_interest=0,
                gateway_name="ZAK2",
            )
        )
    return bars


def _trades_to_dicts(engine: BacktestingEngine) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for trade in engine.trades.values():
        out.append(
            {
                "datetime": trade.datetime.isoformat() if trade.datetime else "",
                "direction": trade.direction.value if trade.direction else "",
                "offset": trade.offset.value if trade.offset else "",
                "price": float(trade.price),
                "volume": float(trade.volume),
            }
        )
    return out


def _daily_rows(engine: BacktestingEngine) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    df = getattr(engine, "daily_df", None)
    if df is None or getattr(df, "empty", True):
        return rows
    for idx, row in df.iterrows():
        # vnpy daily often has end_balance via calculate_statistics path; prefer balance/end_balance
        equity = None
        for key in ("balance", "end_balance", "net_pnl"):
            if key in df.columns:
                equity = float(row[key])
                if key != "net_pnl":
                    break
        if equity is None:
            continue
        # If only net_pnl available, skip — statistics path fills balance later
        if "balance" in df.columns or "end_balance" in df.columns:
            rows.append({"date": str(idx), "balance": float(row.get("balance", row.get("end_balance")))})
    return rows


def run_cta_backtest(
    bar_records: list[dict],
    *,
    vt_symbol: str,
    strategy_id: str,
    setting: dict[str, Any],
    start: str,
    end: str,
    capital: float,
    rate: float,
    slippage: float,
    stamp_duty: float,
    size: int = 1,
    pricetick: float = 0.01,
    interval: str = "d",
) -> dict[str, Any]:
    if not bar_records:
        raise ValueError("历史数据为空")

    strategy_class = get_strategy_class(strategy_id)
    iv = vnpy_interval(interval)
    bars = records_to_bars(bar_records, vt_symbol=vt_symbol, interval=interval)
    engine = AShareBacktestingEngine()
    engine.stamp_duty = float(stamp_duty)
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=iv,
        start=datetime.fromisoformat(start[:10]),
        end=datetime.fromisoformat(end[:10]),
        rate=float(rate),
        slippage=float(slippage),
        size=float(size),
        pricetick=float(pricetick),
        capital=int(capital),
        mode=BacktestingMode.BAR,
    )
    engine.add_strategy(strategy_class, dict(setting))
    engine.history_data = bars
    engine.run_backtesting()
    engine.calculate_result()
    stats = engine.calculate_statistics(output=False) or {}

    # equity from daily_df balance if present
    daily_rows: list[dict[str, Any]] = []
    df = getattr(engine, "daily_df", None)
    if df is not None and not getattr(df, "empty", True):
        bal_col = "balance" if "balance" in df.columns else None
        if bal_col:
            for idx, row in df.iterrows():
                daily_rows.append({"date": str(idx), "balance": float(row[bal_col])})

    # Fallback: synthesize equity from capital + cumulative net_pnl
    if not daily_rows and df is not None and not getattr(df, "empty", True) and "net_pnl" in df.columns:
        cum = float(capital)
        for idx, row in df.iterrows():
            cum += float(row["net_pnl"])
            daily_rows.append({"date": str(idx), "balance": cum})

    mapped = map_vnpy_statistics(dict(stats), trades=_trades_to_dicts(engine), daily_rows=daily_rows)
    # Ensure UI-compatible percent scale: vnpy 4 often returns fraction (0.12) for returns
    for key in ("total_return", "max_drawdown"):
        val = mapped.get(key)
        if val is not None and abs(val) <= 1.5:
            mapped[key] = round(val * 100.0, 4)
            if key in mapped["statistics"]:
                mapped["statistics"][key] = mapped[key]
    for key in ("annual_return", "return_std", "max_ddpercent"):
        if key in mapped["statistics"]:
            v = mapped["statistics"][key]
            if isinstance(v, (int, float)) and abs(v) <= 1.5:
                mapped["statistics"][key] = round(float(v) * 100.0, 4)
    mapped["statistics"]["stamp_duty"] = stamp_duty
    mapped["statistics"]["engine"] = "vnpy"
    return mapped
