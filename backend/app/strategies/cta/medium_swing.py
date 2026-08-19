"""日 K 中线波段 CTA：MACD 金叉/死叉 + 中长期均线趋势过滤。

买入：MACD 金叉（DIF 上穿 DEA）且收盘价站上 trend_ma_window 均线。
卖出：MACD 死叉（DIF 下穿 DEA）或收盘跌破 trend_ma_window 均线。
"""

from __future__ import annotations

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy_ctastrategy.base import StopOrder

from app.strategies.cta.ashare_template import AShareCtaTemplate


class MediumSwingStrategy(AShareCtaTemplate):
    author = "zak2"

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    trend_ma_window: int = 60
    trade_volume: int = 100

    dif0: float = 0.0
    dif1: float = 0.0
    dea0: float = 0.0
    dea1: float = 0.0
    trend_ma0: float = 0.0

    parameters = [
        "fast_period",
        "slow_period",
        "signal_period",
        "trend_ma_window",
        "trade_volume",
    ]
    variables = ["dif0", "dif1", "dea0", "dea1", "trend_ma0"]

    def on_init(self) -> None:
        self.write_log("中线波段策略初始化")
        self.bg = BarGenerator(self.on_bar)
        size = max(int(self.slow_period) * 2, int(self.trend_ma_window)) + 10
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
        min_bars = max(int(self.slow_period) * 2, int(self.trend_ma_window)) + 2
        if am.count < min_bars:
            return

        dif_arr, dea_arr, _macd_arr = am.macd(
            int(self.fast_period),
            int(self.slow_period),
            int(self.signal_period),
            array=True,
        )
        self.dif0 = float(dif_arr[-1])
        self.dif1 = float(dif_arr[-2])
        self.dea0 = float(dea_arr[-1])
        self.dea1 = float(dea_arr[-2])

        trend_ma = am.sma(int(self.trend_ma_window), array=True)
        self.trend_ma0 = float(trend_ma[-1])

        golden_cross = self.dif0 > self.dea0 and self.dif1 <= self.dea1
        dead_cross = self.dif0 < self.dea0 and self.dif1 >= self.dea1

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            if dead_cross or bar.close_price < self.trend_ma0:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
        elif golden_cross and bar.close_price > self.trend_ma0 and volume > 0:
            self.buy_stock(bar.close_price, volume)

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
