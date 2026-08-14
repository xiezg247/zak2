"""A 股 CTA 薄模板：整手 100、T+1 卖出约束。"""

from __future__ import annotations

from datetime import date

from vnpy.trader.constant import Offset
from vnpy.trader.object import BarData, TickData, OrderData, TradeData
from vnpy_ctastrategy import CtaTemplate
from vnpy_ctastrategy.base import StopOrder


class AShareCtaTemplate(CtaTemplate):
    """仅做多；买入整手；卖出受 T+1 限制。"""

    author = "zak2"

    trade_volume: int = 100

    parameters = ["trade_volume"]
    variables: list[str] = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self._lot_buy_dates: dict[date, int] = {}
        self._pending_buy_date: date | None = None

    def round_volume(self, volume: int) -> int:
        lot = 100
        v = int(volume)
        if v < lot:
            return 0
        return (v // lot) * lot

    def buy_stock(self, price: float, volume: int) -> None:
        qty = self.round_volume(volume)
        if qty <= 0:
            return
        self._pending_buy_date = None
        self.buy(price, qty)

    def sell_stock(self, price: float, volume: int, trading_day: date) -> None:
        qty = self.round_volume(volume)
        if qty <= 0:
            return
        available = 0
        for d, q in self._lot_buy_dates.items():
            if d < trading_day:
                available += q
        qty = min(qty, available, abs(int(self.pos)))
        qty = self.round_volume(qty)
        if qty <= 0:
            return
        remain = qty
        for d in sorted(self._lot_buy_dates):
            if remain <= 0:
                break
            if d >= trading_day:
                continue
            take = min(self._lot_buy_dates[d], remain)
            self._lot_buy_dates[d] -= take
            remain -= take
            if self._lot_buy_dates[d] <= 0:
                del self._lot_buy_dates[d]
        self.sell(price, qty)

    def on_trade(self, trade: TradeData) -> None:
        if trade.offset == Offset.OPEN or (
            trade.direction.name == "LONG" and trade.offset == Offset.NONE
        ):
            d = trade.datetime.date() if trade.datetime else date.today()
            self._lot_buy_dates[d] = self._lot_buy_dates.get(d, 0) + int(trade.volume)
        super().on_trade(trade)

    def on_tick(self, tick: TickData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass

    def on_bar(self, bar: BarData) -> None:
        pass
