"""自选策略看板：模式常量与 config_key 解析（strategy_board 拆分）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.strategy.strategy_signal_ma import parse_config_key

DEFAULT_CONFIG_KEY = "AshareShortBreakoutStrategy:5:10"
SIGNAL_MODE_HEURISTIC = "heuristic_v2"
SIGNAL_MODE_DOUBLE_MA = "double_ma"
SIGNAL_MODE_TREND_MA = "trend_ma"
SIGNAL_MODE_MEDIUM_SWING = "medium_swing"
SIGNAL_MODE_DONCHIAN = "donchian"
SIGNAL_MODE_RSI_REVERSAL = "rsi_reversal"
SIGNAL_MODE_BOLLINGER = "bollinger"
SIGNAL_MODE_MA_BAND = "ma_band"
SIGNAL_MODE_ATR_BREAKOUT = "atr_breakout"
ALL_SIGNAL_MODES = frozenset(
    {
        SIGNAL_MODE_HEURISTIC,
        SIGNAL_MODE_DOUBLE_MA,
        SIGNAL_MODE_TREND_MA,
        SIGNAL_MODE_MEDIUM_SWING,
        SIGNAL_MODE_DONCHIAN,
        SIGNAL_MODE_RSI_REVERSAL,
        SIGNAL_MODE_BOLLINGER,
        SIGNAL_MODE_MA_BAND,
        SIGNAL_MODE_ATR_BREAKOUT,
    }
)
DEFAULT_DOUBLE_MA_FAST = 5
DEFAULT_DOUBLE_MA_SLOW = 20
BAR_LIMIT = 120


def bars_limit_for(mode: str, config_key: str) -> int:
    """按模式决定日 K 取数上限。

    heuristic/double_ma 的 slow 可被用户配到 120（见 _pref_fast_slow），
    计算需要 slow + 确认棒；其余策略窗口 ≤62 根，120 根足够。
    """
    if mode in {SIGNAL_MODE_HEURISTIC, SIGNAL_MODE_DOUBLE_MA}:
        fast, slow = parse_config_key(config_key) or (DEFAULT_DOUBLE_MA_FAST, DEFAULT_DOUBLE_MA_SLOW)
        return max(BAR_LIMIT, slow + 2)
    return BAR_LIMIT


def resolve_config_key(db: Session, user_id: str, override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    row = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE user_id = CAST(:uid AS uuid)
              AND namespace = 'watchlist' AND key = 'signal_config'
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).scalar()
    if isinstance(row, dict):
        cls = str(row.get("class_name") or "AshareShortBreakoutStrategy").strip()
        try:
            fast = max(2, min(int(row.get("fast_window") or 5), 60))
            slow = max(fast + 1, min(int(row.get("slow_window") or 10), 120))
        except (TypeError, ValueError):
            return DEFAULT_CONFIG_KEY
        return f"{cls}:{fast}:{slow}"
    return DEFAULT_CONFIG_KEY


def double_ma_config_key(fast: int, slow: int) -> str:
    return f"double_ma:{int(fast)}:{int(slow)}"


def trend_ma_config_key() -> str:
    from app.services.strategy.strategy_signal_ma import TREND_MA_FAST, TREND_MA_SLOW

    return f"trend_ma:{TREND_MA_FAST}:{TREND_MA_SLOW}"


def medium_swing_config_key() -> str:
    from app.services.strategy.strategy_signal_ma import (
        MEDIUM_SWING_FAST,
        MEDIUM_SWING_SLOW,
    )

    return f"medium_swing:{MEDIUM_SWING_FAST}:{MEDIUM_SWING_SLOW}"


def donchian_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import DONCHIAN_ENTRY, DONCHIAN_EXIT

    return f"donchian:{DONCHIAN_ENTRY}:{DONCHIAN_EXIT}"


def rsi_reversal_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import (
        RSI_OVERBOUGHT,
        RSI_OVERSOLD,
        RSI_PERIOD,
    )

    return f"rsi_reversal:{RSI_PERIOD}:{RSI_OVERSOLD}:{RSI_OVERBOUGHT}"


def bollinger_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import BOLL_DEV, BOLL_PERIOD

    return f"bollinger:{BOLL_PERIOD}:{BOLL_DEV}"


def ma_band_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import (
        MA_BAND_FAST,
        MA_BAND_LONG,
        MA_BAND_MID,
        MA_BAND_SLOW,
    )

    return f"ma_band:{MA_BAND_FAST}:{MA_BAND_MID}:{MA_BAND_SLOW}:{MA_BAND_LONG}"


def atr_breakout_config_key() -> str:
    from app.services.strategy.strategy_signal_extra import (
        ATR_CHANNEL_PERIOD,
        ATR_MULT,
        ATR_PERIOD,
    )

    return f"atr_breakout:{ATR_CHANNEL_PERIOD}:{ATR_PERIOD}:{ATR_MULT}"


def _pref_fast_slow(db: Session, user_id: str) -> tuple[int, int]:
    row = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE user_id = CAST(:uid AS uuid)
              AND namespace = 'watchlist' AND key = 'signal_config'
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).scalar()
    if isinstance(row, dict):
        try:
            fast = max(2, min(int(row.get("fast_window") or DEFAULT_DOUBLE_MA_FAST), 60))
            slow = max(
                fast + 1,
                min(int(row.get("slow_window") or DEFAULT_DOUBLE_MA_SLOW), 120),
            )
            return fast, slow
        except (TypeError, ValueError):
            pass
    return DEFAULT_DOUBLE_MA_FAST, DEFAULT_DOUBLE_MA_SLOW


def resolve_board_config_key(
    db: Session,
    user_id: str,
    *,
    signal_mode: str = SIGNAL_MODE_HEURISTIC,
    override: str | None = None,
) -> str:
    mode = (signal_mode or SIGNAL_MODE_HEURISTIC).strip() or SIGNAL_MODE_HEURISTIC
    if override and override.strip():
        return override.strip()
    if mode == SIGNAL_MODE_DOUBLE_MA:
        fast, slow = _pref_fast_slow(db, user_id)
        return double_ma_config_key(fast, slow)
    if mode == SIGNAL_MODE_TREND_MA:
        return trend_ma_config_key()
    if mode == SIGNAL_MODE_MEDIUM_SWING:
        return medium_swing_config_key()
    if mode == SIGNAL_MODE_DONCHIAN:
        return donchian_config_key()
    if mode == SIGNAL_MODE_RSI_REVERSAL:
        return rsi_reversal_config_key()
    if mode == SIGNAL_MODE_BOLLINGER:
        return bollinger_config_key()
    if mode == SIGNAL_MODE_MA_BAND:
        return ma_band_config_key()
    if mode == SIGNAL_MODE_ATR_BREAKOUT:
        return atr_breakout_config_key()
    return resolve_config_key(db, user_id, None)
