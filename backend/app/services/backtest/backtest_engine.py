"""回测策略元数据与历史薄引擎残留（生产已切 vnpy）。"""

from __future__ import annotations

from app.services.backtest.backtest_bars import Bar, load_daily_bars

__all__ = [
    "STRATEGIES",
    "PROFILES",
    "Bar",
    "load_daily_bars",
    "_sma",
]

STRATEGIES = (
    {
        "id": "double_ma",
        "name": "双均线",
        "interval": "d",
        "description": "vnpy CTA：快线上穿慢线买入、下穿卖出；整手 100 股；仅做多；支持 d/1m",
        "scenario": "快慢均线交叉，信号直白；适合趋势初期的标的，但震荡市易来回止损",
        "implemented": True,
        "engine": "vnpy",
    },
    {
        "id": "trend_ma",
        "name": "趋势双均线（ADX）",
        "interval": "d",
        "description": "金叉+ADX过滤买入；死叉/破慢线/追踪止损卖出；整手 T+1；支持 d/1m",
        "scenario": "金叉叠加 ADX 趋势强度过滤并带追踪止损；适合趋势明确、波动较大的标的",
        "implemented": True,
        "engine": "vnpy",
    },
    {
        "id": "medium_swing",
        "name": "中线波段（MACD）",
        "interval": "d",
        "description": "MACD 金叉+站上趋势均线买入；死叉或破趋势均线卖出；整手 T+1；支持 d/1m",
        "scenario": "MACD 结合 60 日趋势均线，过滤短线噪音；适合持仓数周至数月的中期波段",
        "implemented": True,
        "engine": "vnpy",
    },
    {
        "id": "donchian",
        "name": "唐奇安通道突破",
        "interval": "d",
        "description": "收盘突破 N 日新高买入、跌破 M 日新低卖出；整手 T+1；支持 d/1m",
        "scenario": "经典趋势跟踪：追强突破、破位离场；适合趋势行情，震荡市易被反复扫",
        "implemented": True,
        "engine": "vnpy",
    },
    {
        "id": "rsi_reversal",
        "name": "RSI 超卖反转",
        "interval": "d",
        "description": "RSI 自超卖回升买入、自超买回落卖出；整手 T+1；支持 d/1m",
        "scenario": "震荡市低吸高抛为主；趋势市中逆势接刀容易吃亏，建议搭配大周期判断",
        "implemented": True,
        "engine": "vnpy",
    },
    {
        "id": "bollinger",
        "name": "布林带回归",
        "interval": "d",
        "description": "收盘触及下轨买入、触及上轨卖出；整手 T+1；支持 d/1m",
        "scenario": "均值回归思路：适合箱体震荡标的；单边趋势中会逆势，需严控仓位",
        "implemented": True,
        "engine": "vnpy",
    },
    {
        "id": "ma_band",
        "name": "均线多头排列",
        "interval": "d",
        "description": "5/10/20/60 多头排列形成买入；多头破坏或跌破 20 日线卖出；整手 T+1；支持 d/1m",
        "scenario": "慢牛与强势趋势跟随：多头排列持有、转弱即走；适合趋势延续性好的标的",
        "implemented": True,
        "engine": "vnpy",
    },
    {
        "id": "atr_breakout",
        "name": "ATR 波幅突破",
        "interval": "d",
        "description": "收盘穿越 ATR 通道上轨买入、跌破下轨卖出；整手 T+1；支持 d/1m",
        "scenario": "海龟式波动率跟踪：通道宽度随波动自动缩放，适合放量起爆、波动率放大的标的",
        "implemented": True,
        "engine": "vnpy",
    },
)

PROFILES = (
    {
        "profile_id": "ultra_short",
        "name": "极致短线",
        "description": "打板/半路，持仓短",
        "fast_window": 3,
        "slow_window": 8,
        "capital": 100_000,
    },
    {
        "profile_id": "short_swing",
        "name": "短线波段",
        "description": "放量突破为主",
        "fast_window": 5,
        "slow_window": 20,
        "capital": 100_000,
    },
    {
        "profile_id": "medium_watch",
        "name": "中线观察",
        "description": "趋势跟踪辅助",
        "fast_window": 10,
        "slow_window": 30,
        "capital": 100_000,
    },
    {
        "profile_id": "trend",
        "name": "趋势",
        "description": "均线趋势，持仓更长",
        "fast_window": 20,
        "slow_window": 60,
        "capital": 100_000,
    },
)


def _sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if window <= 0:
        return out
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out[i] = s / window
    return out
