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
    f, s = fast_ma[i], slow_ma[i]
    pf, ps = fast_ma[j], slow_ma[j]
    kf, ks = fast_ma[k], slow_ma[k]
    if None in (f, s, pf, ps, kf, ks):
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
    }
    if vol_ratio is not None:
        out["volume_ratio_5d"] = round(vol_ratio, 4)
    return out
