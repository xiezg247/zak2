"""日 K 唐奇安通道突破 CTA：N 日新高买入 / M 日新低卖出（经典趋势跟踪）。"""

from __future__ import annotations

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy.base import StopOrder

from app.strategies.cta.ashare_template import AShareCtaTemplate


class DonchianStrategy(AShareCtaTemplate):
    author = "zak2"

    entry_window: int = 20
    exit_window: int = 10
    trade_volume: int = 100

    entry_price: float = 0.0

    parameters = ["entry_window", "exit_window", "trade_volume"]
    variables = ["entry_price"]

    def on_init(self) -> None:
        self.write_log("唐奇安通道策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=max(int(self.entry_window), int(self.exit_window)) + 10)
        self._highs: list[float] = []
        self._lows: list[float] = []

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
        self._highs.append(bar.high_price)
        self._lows.append(bar.low_price)
        keep = max(int(self.entry_window), int(self.exit_window)) + 1
        if len(self._highs) > keep:
            self._highs = self._highs[-keep:]
            self._lows = self._lows[-keep:]
        if len(self._highs) <= int(self.entry_window):
            return

        # 不含当根：取最近 entry_window 根的通道
        upper = max(self._highs[-(int(self.entry_window) + 1) : -1])
        lower = min(self._lows[-(int(self.exit_window) + 1) : -1])

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            if bar.close_price < lower:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
        elif bar.close_price > upper and volume > 0:
            self.buy_stock(bar.close_price, volume)
            self.entry_price = bar.close_price

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
