"""strategy_board 平铺拆分结构回归：config/calc 符号归属 + 原模块聚合。"""

from __future__ import annotations

from app.services.strategy.strategy_board_calc import (
    _load_daily_bars_map,
    _pack_signal_row,
    _parse_payload,
    _t1_locked,
    enrich_position_risk,
)
from app.services.strategy.strategy_board_config import (
    DEFAULT_CONFIG_KEY,
    ALL_SIGNAL_MODES,
    bars_limit_for,
    resolve_board_config_key,
    resolve_config_key,
)


def test_config_module_exports() -> None:
    assert DEFAULT_CONFIG_KEY.startswith("AshareShortBreakoutStrategy")
    assert len(ALL_SIGNAL_MODES) == 9
    assert callable(resolve_config_key)
    assert callable(resolve_board_config_key)
    assert callable(bars_limit_for)


def test_calc_module_exports() -> None:
    assert callable(_load_daily_bars_map)
    assert callable(_pack_signal_row)
    assert callable(_parse_payload)
    assert callable(_t1_locked)
    assert callable(enrich_position_risk)


def test_strategy_board_still_exposes_all() -> None:
    from app.services.strategy import strategy_board as sb

    for name in (
        "DEFAULT_CONFIG_KEY",
        "SIGNAL_MODE_HEURISTIC",
        "ALL_SIGNAL_MODES",
        "bars_limit_for",
        "resolve_config_key",
        "resolve_board_config_key",
        "_safe_float",
        "_parse_payload",
        "_load_daily_bars_map",
        "_compute_snapshot",
        "_t1_locked",
        "_signal_label",
        "enrich_position_risk",
        "_pack_signal_row",
        "load_strategy_board",
        "get_quote_store",
        "repo",
        "signal_panel_repo",
        "positions_repo",
    ):
        assert hasattr(sb, name), name
