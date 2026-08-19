"""日 K RSI 超卖反转 CTA：超卖回升买入、超买回落卖出（适合震荡市）。"""

from __future__ import annotations

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy.base import StopOrder

from app.strategies.cta.ashare_template import AShareCtaTemplate


class RsiReversalStrategy(AShareCtaTemplate):
    author = "zak2"

    rsi_period: int = 14
    oversold: int = 30
    overbought: int = 70
    trade_volume: int = 100

    rsi0: float = 0.0
    prev_rsi: float = 0.0
    entry_price: float = 0.0

    parameters = ["rsi_period", "oversold", "overbought", "trade_volume"]
    variables = ["rsi0", "prev_rsi", "entry_price"]

    def on_init(self) -> None:
        self.write_log("RSI 反转策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=int(self.rsi_period) * 3 + 10)

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
        if am.count < int(self.rsi_period) + 2:
            return

        rsi_value = float(am.rsi(self.rsi_period))
        self.prev_rsi = self.rsi0
        self.rsi0 = rsi_value

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            if self.prev_rsi >= self.overbought and self.rsi0 < self.overbought:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
        elif (
            self.prev_rsi <= self.oversold
            and self.rsi0 > self.oversold
            and volume > 0
        ):
            self.buy_stock(bar.close_price, volume)
            self.entry_price = bar.close_price

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
