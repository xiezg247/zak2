"""行情快照（TickFlow 形 symbol）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QuoteSnapshot:
    symbol: str
    name: str = ""
    last_price: float = 0.0
    prev_close: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    change_amount: float = 0.0
    change_pct: float = 0.0
    turnover_rate: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    amplitude: float = 0.0
    volume_ratio: float = 0.0
    net_mf_amount: float = 0.0
    limit_times: float = 0.0
    trade_time: str = ""
    industry: str = ""
    total_mv: float = 0.0
    circ_mv: float = 0.0
