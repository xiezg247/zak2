"""日 K 布林带回归 CTA：触及下轨买入、触及上轨卖出（均值回归）。"""

from __future__ import annotations

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy.base import StopOrder

from app.strategies.cta.ashare_template import AShareCtaTemplate


class BollingerStrategy(AShareCtaTemplate):
    author = "zak2"

    boll_period: int = 20
    boll_dev: float = 2.0
    trade_volume: int = 100

    boll_upper: float = 0.0
    boll_lower: float = 0.0
    entry_price: float = 0.0

    parameters = ["boll_period", "boll_dev", "trade_volume"]
    variables = ["boll_upper", "boll_lower", "entry_price"]

    def on_init(self) -> None:
        self.write_log("布林带策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=int(self.boll_period) * 2 + 10)

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
        if am.count < int(self.boll_period) + 2:
            return

        upper, lower = am.boll(self.boll_period, self.boll_dev)
        self.boll_upper = float(upper)
        self.boll_lower = float(lower)

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            if bar.close_price > self.boll_upper:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
        elif bar.close_price < self.boll_lower and volume > 0:
            self.buy_stock(bar.close_price, volume)
            self.entry_price = bar.close_price

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
