"""日 K 双均线 CTA（语义对齐桌面 AshareDoubleMaStrategy，不 import zak）。"""

from __future__ import annotations

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy.base import StopOrder

from app.strategies.cta.ashare_template import AShareCtaTemplate


class DoubleMaStrategy(AShareCtaTemplate):
    author = "zak2"

    fast_window: int = 10
    slow_window: int = 20
    trade_volume: int = 100

    fast_ma0: float = 0.0
    fast_ma1: float = 0.0
    slow_ma0: float = 0.0
    slow_ma1: float = 0.0

    parameters = ["fast_window", "slow_window", "trade_volume"]
    variables = ["fast_ma0", "fast_ma1", "slow_ma0", "slow_ma1"]

    def on_init(self) -> None:
        self.write_log("双均线策略初始化")
        self.bg = BarGenerator(self.on_bar)
        size = max(int(self.fast_window), int(self.slow_window)) + 10
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
        if not am.inited:
            return
        if max(self.fast_window, self.slow_window) > am.count:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = float(fast_ma[-1])
        self.fast_ma1 = float(fast_ma[-2])

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = float(slow_ma[-1])
        self.slow_ma1 = float(slow_ma[-2])

        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 <= self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 >= self.slow_ma1

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if cross_over:
            self.buy_stock(bar.close_price, volume)
        elif cross_below:
            self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
