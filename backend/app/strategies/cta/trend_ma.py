"""日 K 趋势双均线 + ADX + 追踪止损（对齐桌面 AshareTrendMaStrategy，不 import zak）。"""

from __future__ import annotations

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy.base import StopOrder

from app.strategies.cta.ashare_template import AShareCtaTemplate


class TrendMaStrategy(AShareCtaTemplate):
    author = "zak2"

    fast_window: int = 20
    slow_window: int = 60
    adx_period: int = 14
    adx_threshold: float = 25.0
    trailing_stop_pct: float = 0.12
    trade_volume: int = 100

    fast_ma0: float = 0.0
    fast_ma1: float = 0.0
    slow_ma0: float = 0.0
    slow_ma1: float = 0.0
    adx_value: float = 0.0
    highest_since_entry: float = 0.0
    entry_price: float = 0.0

    parameters = [
        "fast_window",
        "slow_window",
        "adx_period",
        "adx_threshold",
        "trailing_stop_pct",
        "trade_volume",
    ]
    variables = [
        "fast_ma0",
        "fast_ma1",
        "slow_ma0",
        "slow_ma1",
        "adx_value",
        "highest_since_entry",
        "entry_price",
    ]

    def on_init(self) -> None:
        self.write_log("趋势均线策略初始化")
        self.bg = BarGenerator(self.on_bar)
        size = max(int(self.slow_window), int(self.adx_period) * 2) + 10
        self.am = ArrayManager(size=size)

    def on_start(self) -> None:
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self) -> None:
        self.write_log("策略停止")
        self.put_event()

    def on_bar(self, bar: BarData) -> None:
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        min_bars = max(int(self.slow_window), int(self.adx_period) * 2) + 2
        if am.count < min_bars:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = float(fast_ma[-1])
        self.fast_ma1 = float(fast_ma[-2])

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = float(slow_ma[-1])
        self.slow_ma1 = float(slow_ma[-2])

        self.adx_value = float(am.adx(self.adx_period))

        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 <= self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 >= self.slow_ma1

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            self.highest_since_entry = max(self.highest_since_entry, bar.close_price)
            trail_stop = self.highest_since_entry * (1 - self.trailing_stop_pct)
            structure_break = bar.close_price < self.slow_ma0
            if cross_below or structure_break or bar.close_price < trail_stop:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.highest_since_entry = 0.0
        elif (
            cross_over
            and self.adx_value >= self.adx_threshold
            and bar.close_price > self.slow_ma0
            and self.slow_ma0 >= self.slow_ma1
        ):
            if volume > 0:
                self.buy_stock(bar.close_price, volume)
                self.entry_price = bar.close_price
                self.highest_since_entry = bar.close_price

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
