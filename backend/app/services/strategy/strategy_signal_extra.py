"""日 K 扩展 CTA 策略信号（唐奇安/RSI 反转/布林回归/均线多头/ATR 突破）。

对齐回测同名策略的入场/出场规则，输出结构与 strategy_signal_ma 一致。
"""

from __future__ import annotations

from typing import Any

from app.services.strategy.strategy_signal_ma import _LABEL, sma, strength_tier_for

# donchian
DONCHIAN_ENTRY = 20
DONCHIAN_EXIT = 10
# rsi_reversal
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
# bollinger
BOLL_PERIOD = 20
BOLL_DEV = 2.0
# ma_band
MA_BAND_FAST = 5
MA_BAND_MID = 10
MA_BAND_SLOW = 20
MA_BAND_LONG = 60
# atr_breakout
ATR_CHANNEL_PERIOD = 20
ATR_PERIOD = 14
ATR_MULT = 2.0


def wilder_rsi(closes: list[float], period: int) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    if period < 1 or n <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi(gain: float, loss: float) -> float:
        if loss == 0.0:
            return 100.0
        return 100.0 * gain / (gain + loss)

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i + 1] = _rsi(avg_gain, avg_loss)
    return out


def wilder_atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int,
) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    if period < 1 or n <= period or len(highs) != n or len(lows) != n:
        return out
    trs = [0.0] * n
    for i in range(1, n):
        trs[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    value = sum(trs[1 : period + 1]) / period
    out[period] = value
    for i in range(period + 1, n):
        value = (value * (period - 1) + trs[i]) / period
        out[i] = value
    return out


def bollinger_bands(
    closes: list[float],
    period: int,
    dev: float,
) -> tuple[list[float | None], list[float | None]]:
    """返回 (upper, lower)，标准差用样本标准差（ddof=1，对齐 vnpy ArrayManager.std）。"""
    mid = sma(closes, period)
    n = len(closes)
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    for i in range(period - 1, n):
        m = mid[i]
        if m is None:
            continue
        window = closes[i - period + 1 : i + 1]
        var = sum((v - m) ** 2 for v in window) / (period - 1)
        std = var**0.5
        upper[i] = m + dev * std
        lower[i] = m - dev * std
    return upper, lower


def _vol_ratio_5d(volumes: list[float] | None, closes: list[float]) -> float | None:
    if not volumes or len(volumes) != len(closes) or len(volumes) < 5:
        return None
    last = volumes[-1]
    avg5 = sum(volumes[-5:]) / 5.0
    if avg5 <= 0:
        return None
    return last / avg5


def _attach_vol_ratio(snap: dict[str, Any], volumes: list[float] | None, closes: list[float]) -> dict[str, Any]:
    ratio = _vol_ratio_5d(volumes, closes)
    if ratio is not None:
        snap["volume_ratio_5d"] = round(ratio, 4)
    return snap


def compute_donchian_signal(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    entry_window: int = DONCHIAN_ENTRY,
    exit_window: int = DONCHIAN_EXIT,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    """唐奇安通道：收盘突破前 N 日新高买入 / 跌破前 M 日新低卖出，对齐回测 donchian。"""
    n = len(closes)
    if n <= entry_window or len(highs) != n or len(lows) != n:
        return None
    i = n - 1
    upper = max(highs[i - entry_window : i])
    lower = min(lows[i - exit_window : i])
    close = closes[i]

    if close < lower:
        kind = "sell"
    elif close > upper:
        kind = "buy"
    else:
        kind = "hold"

    gap = (close - upper) / upper * 100.0 if upper else 0.0
    if kind == "sell":
        gap = (lower - close) / lower * 100.0 if lower else 0.0
    gap_abs = abs(gap)
    tier, tier_label = strength_tier_for(gap_abs)

    if kind == "buy":
        reason = f"收盘突破{entry_window}日新高（唐奇安通道·{tier_label}）"
    elif kind == "sell":
        reason = f"收盘跌破{exit_window}日新低（唐奇安通道·{tier_label}）"
    else:
        reason = f"通道内观望（唐奇安通道·{tier_label}）"

    snap: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": close,
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": 0,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
        "signal_mode": "donchian",
        "channel_upper": round(float(upper), 4),
        "channel_lower": round(float(lower), 4),
    }
    return _attach_vol_ratio(snap, volumes, closes)


def compute_rsi_reversal_signal(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    rsi_period: int = RSI_PERIOD,
    oversold: int = RSI_OVERSOLD,
    overbought: int = RSI_OVERBOUGHT,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    """RSI 超卖回升买入 / 超买回落卖出，对齐回测 rsi_reversal。"""
    n = len(closes)
    if n <= rsi_period + 1:
        return None
    rsi_arr = wilder_rsi(closes, rsi_period)
    i = n - 1
    r0 = rsi_arr[i]
    r1 = rsi_arr[i - 1]
    if r0 is None or r1 is None:
        return None

    if r1 >= overbought and r0 < overbought:
        kind = "sell"
    elif r1 <= oversold and r0 > oversold:
        kind = "buy"
    else:
        kind = "hold"

    gap = r0 - 50.0
    gap_abs = abs(gap) / 100.0 * 100.0
    tier, tier_label = strength_tier_for(gap_abs)

    if kind == "buy":
        reason = f"RSI 自超卖回升（{rsi_period} 日·{tier_label}）"
    elif kind == "sell":
        reason = f"RSI 自超买回落（{rsi_period} 日·{tier_label}）"
    else:
        reason = f"RSI {r0:.1f} 观望（{rsi_period} 日·{tier_label}）"

    snap: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": closes[i],
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": 0,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
        "signal_mode": "rsi_reversal",
        "rsi_value": round(float(r0), 4),
    }
    return _attach_vol_ratio(snap, volumes, closes)


def compute_bollinger_signal(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    boll_period: int = BOLL_PERIOD,
    boll_dev: float = BOLL_DEV,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    """布林带回归：收盘触及下轨买入 / 触及上轨卖出，对齐回测 bollinger。"""
    n = len(closes)
    if n <= boll_period + 1:
        return None
    upper, lower = bollinger_bands(closes, boll_period, boll_dev)
    i = n - 1
    upper_v = upper[i]
    lower_v = lower[i]
    if upper_v is None or lower_v is None:
        return None
    close = closes[i]

    if close > upper_v:
        kind = "sell"
    elif close < lower_v:
        kind = "buy"
    else:
        kind = "hold"

    mid = (upper_v + lower_v) / 2.0
    gap = (close - mid) / mid * 100.0 if mid else 0.0
    gap_abs = abs(gap)
    tier, tier_label = strength_tier_for(gap_abs)

    if kind == "buy":
        reason = f"收盘触及布林下轨（{boll_period} 日 ±{boll_dev}σ·{tier_label}）"
    elif kind == "sell":
        reason = f"收盘触及布林上轨（{boll_period} 日 ±{boll_dev}σ·{tier_label}）"
    else:
        reason = f"布林带内观望（{boll_period} 日 ±{boll_dev}σ·{tier_label}）"

    snap: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": close,
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": 0,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
        "signal_mode": "bollinger",
        "boll_upper": round(float(upper_v), 4),
        "boll_lower": round(float(lower_v), 4),
    }
    return _attach_vol_ratio(snap, volumes, closes)


def compute_ma_band_signal(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    ma_fast: int = MA_BAND_FAST,
    ma_mid: int = MA_BAND_MID,
    ma_slow: int = MA_BAND_SLOW,
    ma_long: int = MA_BAND_LONG,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    """均线多头排列：5/10/20/60 多头形成买入，多头破坏/跌破 20 日线卖出，对齐回测 ma_band。"""
    n = len(closes)
    if n <= ma_long + 1 or not (ma_fast < ma_mid < ma_slow < ma_long):
        return None
    fast_arr = sma(closes, ma_fast)
    mid_arr = sma(closes, ma_mid)
    slow_arr = sma(closes, ma_slow)
    long_arr = sma(closes, ma_long)
    i = n - 1
    j = i - 1
    f0, f1 = fast_arr[i], fast_arr[j]
    m0, m1 = mid_arr[i], mid_arr[j]
    s0 = slow_arr[i]
    l0 = long_arr[i]
    if any(v is None for v in (f0, f1, m0, m1, s0, l0)):
        return None

    close = closes[i]
    if f0 < m0 or close < s0:
        kind = "sell"
    elif f0 > m0 and f1 <= m1 and m0 > s0 and s0 > l0:
        kind = "buy"
    else:
        kind = "hold"

    gap = (close - l0) / l0 * 100.0 if l0 else 0.0
    gap_abs = abs(gap)
    tier, tier_label = strength_tier_for(gap_abs)

    if kind == "buy":
        reason = f"{ma_fast}/{ma_mid}/{ma_slow}/{ma_long} 多头排列形成（均线多头·{tier_label}）"
    elif kind == "sell":
        reason = f"多头破坏/跌破{ma_slow}日线（均线多头·{tier_label}）"
    else:
        reason = f"均线观望（{ma_fast}/{ma_mid}/{ma_slow}/{ma_long}·{tier_label}）"

    snap: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": close,
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": 0,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
        "signal_mode": "ma_band",
    }
    return _attach_vol_ratio(snap, volumes, closes)


def compute_atr_breakout_signal(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    channel_period: int = ATR_CHANNEL_PERIOD,
    atr_period: int = ATR_PERIOD,
    atr_mult: float = ATR_MULT,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    """ATR 波幅突破：收盘穿越 ATR 通道上轨买入 / 跌破下轨卖出，对齐回测 atr_breakout。"""
    n = len(closes)
    min_bars = max(channel_period, atr_period * 2) + 2
    if n <= min_bars or len(highs) != n or len(lows) != n:
        return None
    mid_arr = sma(closes, channel_period)
    atr_arr = wilder_atr(highs, lows, closes, atr_period)
    i = n - 1
    mid = mid_arr[i]
    atr_v = atr_arr[i]
    if mid is None or atr_v is None:
        return None

    upper = mid + atr_mult * atr_v
    lower = mid - atr_mult * atr_v
    close = closes[i]

    if close < lower:
        kind = "sell"
    elif close > upper:
        kind = "buy"
    else:
        kind = "hold"

    gap = (close - mid) / mid * 100.0 if mid else 0.0
    gap_abs = abs(gap)
    tier, tier_label = strength_tier_for(gap_abs)

    if kind == "buy":
        reason = f"收盘突破 ATR 通道上轨（{channel_period} 日±{atr_mult}ATR·{tier_label}）"
    elif kind == "sell":
        reason = f"收盘跌破 ATR 通道下轨（{channel_period} 日±{atr_mult}ATR·{tier_label}）"
    else:
        reason = f"ATR 通道内观望（{channel_period} 日±{atr_mult}ATR·{tier_label}）"

    snap: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": close,
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": 0,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
        "signal_mode": "atr_breakout",
        "atr_value": round(float(atr_v), 4),
        "channel_upper": round(float(upper), 4),
        "channel_lower": round(float(lower), 4),
    }
    return _attach_vol_ratio(snap, volumes, closes)
