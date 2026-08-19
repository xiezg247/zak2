"""日 K 均线多头排列 CTA：5/10/20/60 多头形成买入，多头破坏/跌破慢线卖出。"""

from __future__ import annotations

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy.base import StopOrder

from app.strategies.cta.ashare_template import AShareCtaTemplate


class MaBandStrategy(AShareCtaTemplate):
    author = "zak2"

    ma_fast: int = 5
    ma_mid: int = 10
    ma_slow: int = 20
    ma_long: int = 60
    trade_volume: int = 100

    fast0: float = 0.0
    fast1: float = 0.0
    mid0: float = 0.0
    mid1: float = 0.0
    slow0: float = 0.0
    long0: float = 0.0
    entry_price: float = 0.0

    parameters = ["ma_fast", "ma_mid", "ma_slow", "ma_long", "trade_volume"]
    variables = ["fast0", "fast1", "mid0", "mid1", "slow0", "long0", "entry_price"]

    def on_init(self) -> None:
        self.write_log("均线多头策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=int(self.ma_long) + 10)

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
        if am.count < int(self.ma_long) + 2:
            return

        fast_arr = am.sma(self.ma_fast, array=True)
        mid_arr = am.sma(self.ma_mid, array=True)
        slow_arr = am.sma(self.ma_slow, array=True)
        long_arr = am.sma(self.ma_long, array=True)

        self.fast0 = float(fast_arr[-1])
        self.fast1 = float(fast_arr[-2])
        self.mid0 = float(mid_arr[-1])
        self.mid1 = float(mid_arr[-2])
        self.slow0 = float(slow_arr[-1])
        self.long0 = float(long_arr[-1])

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            if self.fast0 < self.mid0 or bar.close_price < self.slow0:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
        elif (
            self.fast0 > self.mid0
            and self.fast1 <= self.mid1
            and self.mid0 > self.slow0
            and self.slow0 > self.long0
            and volume > 0
        ):
            self.buy_stock(bar.close_price, volume)
            self.entry_price = bar.close_price

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
