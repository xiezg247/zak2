"""日 K 双均线启发式信号（非桌面 ShortBreakout）。"""

from __future__ import annotations

from typing import Any

CONFIRM_BARS = 2


def sma(values: list[float], window: int) -> list[float | None]:
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


def parse_config_key(config_key: str) -> tuple[int, int] | None:
    parts = (config_key or "").strip().split(":")
    if len(parts) < 3:
        return None
    try:
        fast = int(parts[-2])
        slow = int(parts[-1])
    except ValueError:
        return None
    if fast < 2 or slow <= fast or slow > 120:
        return None
    return fast, slow


def cross_kind(pf: float, ps: float, f: float, s: float) -> str:
    if pf <= ps and f > s:
        return "buy"
    if pf >= ps and f < s:
        return "sell"
    return "hold"


def strength_tier_for(gap_abs: float) -> tuple[str, str]:
    if gap_abs < 0.3:
        return "weak", "弱"
    if gap_abs < 1.0:
        return "mid", "中"
    return "strong", "强"


_LABEL = {"buy": "买入", "sell": "卖出", "hold": "观望"}


def compute_ma_signal(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    fast: int,
    slow: int,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    if fast >= slow or len(closes) < slow + CONFIRM_BARS:
        return None
    fast_ma = sma(closes, fast)
    slow_ma = sma(closes, slow)
    i = len(closes) - 1
    j = i - 1
    k = i - 2
    f = fast_ma[i]
    s = slow_ma[i]
    pf = fast_ma[j]
    ps = slow_ma[j]
    kf = fast_ma[k]
    ks = slow_ma[k]
    if f is None or s is None or pf is None or ps is None or kf is None or ks is None:
        return None

    same_day = cross_kind(pf, ps, f, s)
    prev_cross = cross_kind(kf, ks, pf, ps)

    if same_day in {"buy", "sell"}:
        kind = "hold"
        pending = True
        pending_kind = same_day
    elif prev_cross == "buy" and f > s:
        kind = "buy"
        pending = False
        pending_kind = "buy"
    elif prev_cross == "sell" and f < s:
        kind = "sell"
        pending = False
        pending_kind = "sell"
    else:
        kind = "hold"
        pending = False
        pending_kind = "hold"

    gap = (f - s) / s * 100.0 if s else 0.0
    gap_abs = abs(gap)
    tier, tier_label = strength_tier_for(gap_abs)

    vol_ratio = None
    if volumes and len(volumes) == len(closes) and len(volumes) >= 5:
        last = volumes[-1]
        avg5 = sum(volumes[-5:]) / 5.0
        if avg5 > 0:
            vol_ratio = last / avg5

    reason = f"{fast}/{slow} 日均线"
    if pending and pending_kind == "buy":
        reason += f"金叉待确认（启发式·{tier_label}）"
    elif pending and pending_kind == "sell":
        reason += f"死叉待确认（启发式·{tier_label}）"
    elif kind == "buy":
        reason += f"金叉已确认（启发式·{tier_label}）"
    elif kind == "sell":
        reason += f"死叉已确认（启发式·{tier_label}）"
    else:
        reason += f"持有/观望（启发式·{tier_label}）"

    out: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": closes[-1],
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": CONFIRM_BARS,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
        "signal_mode": "heuristic_v2",
    }
    if vol_ratio is not None:
        out["volume_ratio_5d"] = round(vol_ratio, 4)
    return out


def compute_double_ma_signal(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    fast: int,
    slow: int,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    """当日交叉买卖，对齐回测 double_ma（无确认棒）。"""
    if fast >= slow or len(closes) < slow + 1:
        return None
    fast_ma = sma(closes, fast)
    slow_ma = sma(closes, slow)
    i = len(closes) - 1
    j = i - 1
    f = fast_ma[i]
    s = slow_ma[i]
    pf = fast_ma[j]
    ps = slow_ma[j]
    if f is None or s is None or pf is None or ps is None:
        return None

    kind = cross_kind(pf, ps, f, s)
    gap = (f - s) / s * 100.0 if s else 0.0
    gap_abs = abs(gap)
    tier, tier_label = strength_tier_for(gap_abs)

    vol_ratio = None
    if volumes and len(volumes) == len(closes) and len(volumes) >= 5:
        last = volumes[-1]
        avg5 = sum(volumes[-5:]) / 5.0
        if avg5 > 0:
            vol_ratio = last / avg5

    if kind == "buy":
        reason = f"{fast}/{slow} 日均线金叉（双均线当日交叉（对齐回测 double_ma）·{tier_label}）"
    elif kind == "sell":
        reason = f"{fast}/{slow} 日均线死叉（双均线当日交叉（对齐回测 double_ma）·{tier_label}）"
    else:
        reason = f"{fast}/{slow} 日均线观望（双均线当日交叉（对齐回测 double_ma）·{tier_label}）"

    out: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": closes[-1],
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": 0,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
        "signal_mode": "double_ma",
    }
    if vol_ratio is not None:
        out["volume_ratio_5d"] = round(vol_ratio, 4)
    return out


TREND_MA_FAST = 20
TREND_MA_SLOW = 60
TREND_ADX_PERIOD = 14
TREND_ADX_THRESHOLD = 25.0
TREND_TRAILING_STOP_PCT = 0.12


def wilder_adx(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int,
) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    if period < 1 or n < period * 2 or len(highs) != n or len(lows) != n:
        return out

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    atr = sum(tr[1 : period + 1])
    apdm = sum(plus_dm[1 : period + 1])
    amdm = sum(minus_dm[1 : period + 1])

    def _dx(a: float, b: float, t: float) -> float:
        if t <= 0:
            return 0.0
        pdi = 100.0 * a / t
        mdi = 100.0 * b / t
        s = pdi + mdi
        return 0.0 if s <= 0 else 100.0 * abs(pdi - mdi) / s

    dx_vals: list[float | None] = [None] * n
    dx_vals[period] = _dx(apdm, amdm, atr)
    for i in range(period + 1, n):
        atr = atr - atr / period + tr[i]
        apdm = apdm - apdm / period + plus_dm[i]
        amdm = amdm - amdm / period + minus_dm[i]
        dx_vals[i] = _dx(apdm, amdm, atr)

    first = 2 * period - 1
    if first >= n:
        return out
    seed = [d for d in dx_vals[period : first + 1] if d is not None]
    if len(seed) < period:
        return out
    adx = sum(seed) / period
    out[first] = adx
    for i in range(first + 1, n):
        d = dx_vals[i]
        if d is None:
            continue
        adx = (adx * (period - 1) + d) / period
        out[i] = adx
    return out


def compute_trend_ma_signal(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    fast: int = TREND_MA_FAST,
    slow: int = TREND_MA_SLOW,
    adx_period: int = TREND_ADX_PERIOD,
    adx_threshold: float = TREND_ADX_THRESHOLD,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    """入场对齐 CTA trend_ma；无仓卖点不含追踪止损。"""
    min_bars = max(slow, adx_period * 2) + 2
    if fast >= slow or len(closes) < min_bars:
        return None
    if len(highs) != len(closes) or len(lows) != len(closes):
        return None

    fast_ma = sma(closes, fast)
    slow_ma = sma(closes, slow)
    adx_arr = wilder_adx(highs, lows, closes, adx_period)
    i = len(closes) - 1
    j = i - 1
    f = fast_ma[i]
    s = slow_ma[i]
    pf = fast_ma[j]
    ps = slow_ma[j]
    adx_v = adx_arr[i]
    if f is None or s is None or pf is None or ps is None or adx_v is None:
        return None

    cross = cross_kind(pf, ps, f, s)
    close = closes[i]
    slow_up = s >= ps
    if cross == "buy" and adx_v >= adx_threshold and close > s and slow_up:
        kind = "buy"
    elif cross == "sell" or close < s:
        kind = "sell"
    else:
        kind = "hold"

    gap = (f - s) / s * 100.0 if s else 0.0
    gap_abs = abs(gap)
    tier, tier_label = strength_tier_for(gap_abs)

    vol_ratio = None
    if volumes and len(volumes) == len(closes) and len(volumes) >= 5:
        last = volumes[-1]
        avg5 = sum(volumes[-5:]) / 5.0
        if avg5 > 0:
            vol_ratio = last / avg5

    tag = f"趋势均线看盘（对齐入场；卖点不含追踪止损）·{tier_label}"
    if kind == "buy":
        reason = f"{fast}/{slow} 日均线金叉（{tag}）"
    elif kind == "sell":
        reason = f"{fast}/{slow} 日均线卖出（{tag}）"
    else:
        reason = f"{fast}/{slow} 日均线观望（{tag}）"

    out: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": closes[-1],
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": 0,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
        "signal_mode": "trend_ma",
        "adx_value": round(float(adx_v), 4),
    }
    if vol_ratio is not None:
        out["volume_ratio_5d"] = round(vol_ratio, 4)
    return out
