"""日 K ATR 波幅突破 CTA：收盘穿越 ATR 通道买入、跌破下轨卖出（海龟式）。"""

from __future__ import annotations

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy.base import StopOrder

from app.strategies.cta.ashare_template import AShareCtaTemplate


class AtrBreakoutStrategy(AShareCtaTemplate):
    author = "zak2"

    channel_period: int = 20
    atr_period: int = 14
    atr_mult: float = 2.0
    trade_volume: int = 100

    channel_mid: float = 0.0
    atr_value: float = 0.0
    entry_price: float = 0.0

    parameters = ["channel_period", "atr_period", "atr_mult", "trade_volume"]
    variables = ["channel_mid", "atr_value", "entry_price"]

    def on_init(self) -> None:
        self.write_log("ATR 突破策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=max(int(self.channel_period) * 2, int(self.atr_period) * 3) + 10)

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
        min_bars = max(int(self.channel_period), int(self.atr_period) * 2) + 2
        if am.count < min_bars:
            return

        mid_arr = am.sma(self.channel_period, array=True)
        self.channel_mid = float(mid_arr[-1])
        self.atr_value = float(am.atr(self.atr_period))
        upper = self.channel_mid + self.atr_mult * self.atr_value
        lower = self.channel_mid - self.atr_mult * self.atr_value

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
