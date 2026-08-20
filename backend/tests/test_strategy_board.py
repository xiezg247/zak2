from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.strategy.strategy_board import (
    DEFAULT_CONFIG_KEY,
    _pack_signal_row,
    _parse_payload,
    _t1_locked,
    enrich_position_risk,
    resolve_config_key,
)


def test_parse_payload_envelope() -> None:
    raw = (
        '{"payload": "{\\"vt_symbol\\": \\"600519.SSE\\", \\"signal\\": \\"buy\\", '
        '\\"strength\\": 80}", "bar_as_of": "2026-08-05", "updated_at": "t"}'
    )
    snap = _parse_payload(raw)
    assert snap is not None
    assert snap["signal"] == "buy"
    assert snap["_bar_as_of"] == "2026-08-05"


def test_parse_payload_plain() -> None:
    snap = _parse_payload('{"vt_symbol": "1.SSE", "signal": "hold"}')
    assert snap is not None
    assert snap["signal"] == "hold"


def test_pack_signal_row() -> None:
    row = _pack_signal_row(
        "600519.SSE",
        {"signal": "buy", "strength": 70, "reason_summary": "突破", "as_of": "2026-08-05"},
        name="茅台",
        last_price=1800.0,
        change_pct=1.2,
    )
    assert row["signal_label"] == "买入"
    assert row["name"] == "茅台"
    assert row["strength"] == 70


def test_pack_signal_row_includes_tier() -> None:
    row = _pack_signal_row(
        "600519.SSE",
        {
            "signal": "buy",
            "signal_label": "买入",
            "strength": 0.8,
            "strength_tier": "mid",
            "strength_tier_label": "中",
            "reason_summary": "金叉已确认",
        },
    )
    assert row["strength_tier"] == "mid"
    assert row["strength_tier_label"] == "中"


def test_t1_locked_today() -> None:
    from datetime import datetime, timedelta, timezone

    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    assert _t1_locked(today) is True
    assert _t1_locked("2020-01-01") is False


def test_resolve_config_key_default() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    assert resolve_config_key(db, "u1") == DEFAULT_CONFIG_KEY


def test_resolve_config_key_from_pref() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = {
        "class_name": "AshareShortBreakoutStrategy",
        "fast_window": 5,
        "slow_window": 20,
    }
    assert resolve_config_key(db, "u1") == "AshareShortBreakoutStrategy:5:20"


def test_resolve_board_config_key_double_ma_default() -> None:
    from app.services.strategy.strategy_board import resolve_board_config_key

    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    assert resolve_board_config_key(db, "u1", signal_mode="double_ma") == "double_ma:5:20"


def test_resolve_board_config_key_double_ma_from_pref() -> None:
    from app.services.strategy.strategy_board import resolve_board_config_key

    db = MagicMock()
    db.execute.return_value.scalar.return_value = {
        "class_name": "AshareShortBreakoutStrategy",
        "fast_window": 5,
        "slow_window": 10,
    }
    assert resolve_board_config_key(db, "u1", signal_mode="double_ma") == "double_ma:5:10"


def test_resolve_board_config_key_trend_ma_fixed() -> None:
    from app.services.strategy.strategy_board import resolve_board_config_key

    db = MagicMock()
    assert resolve_board_config_key(db, "u1", signal_mode="trend_ma") == "trend_ma:20:60"


def test_resolve_board_config_key_medium_swing_fixed() -> None:
    from app.services.strategy.strategy_board import resolve_board_config_key

    db = MagicMock()
    assert resolve_board_config_key(db, "u1", signal_mode="medium_swing") == "medium_swing:12:26"


def test_resolve_board_config_key_extended_modes() -> None:
    from app.services.strategy.strategy_board import resolve_board_config_key

    db = MagicMock()
    assert resolve_board_config_key(db, "u1", signal_mode="donchian") == "donchian:20:10"
    assert resolve_board_config_key(db, "u1", signal_mode="rsi_reversal") == "rsi_reversal:14:30:70"
    assert resolve_board_config_key(db, "u1", signal_mode="bollinger") == "bollinger:20:2.0"
    assert resolve_board_config_key(db, "u1", signal_mode="ma_band") == "ma_band:5:10:20:60"
    assert resolve_board_config_key(db, "u1", signal_mode="atr_breakout") == "atr_breakout:20:14:2.0"


def test_bars_limit_default_120() -> None:
    from app.services.strategy.strategy_board import BAR_LIMIT, bars_limit_for

    assert BAR_LIMIT == 120
    assert bars_limit_for("heuristic_v2", "AshareShortBreakoutStrategy:5:10") == 120
    assert bars_limit_for("donchian", "donchian:20:10") == 120
    assert bars_limit_for("trend_ma", "trend_ma:20:60") == 120


def test_bars_limit_grows_with_slow() -> None:
    from app.services.strategy.strategy_board import bars_limit_for

    assert bars_limit_for("heuristic_v2", "AshareShortBreakoutStrategy:5:120") == 122
    assert bars_limit_for("double_ma", "double_ma:60:120") == 122
    assert bars_limit_for("double_ma", "double_ma:8:21") == 120


def test_enrich_position_risk_float_loss() -> None:
    out = enrich_position_risk(
        {"exit_signal": "hold", "unrealized_pnl_pct": -6.0},
        change_pct=None,
        volume_ratio=None,
    )
    assert "浮亏" in out["risk_tags"]
    assert out["risk_primary"] == "浮亏"


def test_enrich_position_risk_sell_with_quote_zero() -> None:
    out = enrich_position_risk(
        {"exit_signal": "sell", "unrealized_pnl_pct": None},
        change_pct=0.0,
        volume_ratio=0.0,
    )
    assert out["risk_tags"] == ["卖出信号"]
    assert out["risk_primary"] == "卖出信号"


def test_enrich_position_risk_no_quote_skips_intraday() -> None:
    out = enrich_position_risk(
        {"exit_signal": "hold", "unrealized_pnl_pct": -6.0},
        change_pct=None,
        volume_ratio=None,
    )
    assert "浮亏" in out["risk_tags"]
    assert "急跌" not in out["risk_tags"]
    assert "大涨" not in out["risk_tags"]


def _mock_db() -> MagicMock:
    db = MagicMock()

    def _execute(stmt, params=None):
        _ = params
        result = MagicMock()
        sql = str(stmt)
        if "user_preferences" in sql:
            result.scalar.return_value = None
        else:
            result.mappings.return_value.all.return_value = []
            result.mappings.return_value.first.return_value = None
        return result

    db.execute.side_effect = _execute
    return db


def _risk_prefs():
    return SimpleNamespace(
        total_capital=None,
        stop_loss_pct=0.05,
        caution_float_pct=-5.0,
        realized_pnl_today=None,
    )


def test_load_strategy_board_empty() -> None:
    from app.services.strategy import strategy_board

    db = _mock_db()
    with (
        patch.object(strategy_board.repo.WatchlistItemRepository, "list_items", return_value=[]),
        patch.object(strategy_board.signal_panel_repo.SignalPanelRepository, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_load_daily_bars_map", return_value={}),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy.strategy_board.load_trading_risk_prefs",
            return_value=_risk_prefs(),
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    assert out["config_key"] == DEFAULT_CONFIG_KEY
    assert out["signals"] == []
    assert out["positions"] == []
    assert out["panel_symbols"] == []
    assert out["source"] == "live"
    assert out["note"]
    assert "warm_watchlist_strategy_cache" not in out["note"]
    assert "实时按日 K 计算" in out["note"]
    rs = out["risk_summary"]
    assert rs["total_capital"] is None
    assert rs["actual_position_pct"] is None


def test_load_strategy_board_live_signal() -> None:
    from app.services.strategy import strategy_board

    db = _mock_db()
    with (
        patch.object(
            strategy_board.repo.WatchlistItemRepository,
            "list_items",
            return_value=[SimpleNamespace(symbol="600519", exchange="SSE", name="茅台")],
        ),
        patch.object(
            strategy_board.signal_panel_repo.SignalPanelRepository,
            "load_symbols",
            return_value=["600519.SSE"],
        ),
        patch.object(
            strategy_board,
            "_load_daily_bars_map",
            return_value={
                "600519.SSE": {
                    "highs": [10.0],
                    "lows": [9.0],
                    "closes": [10.0],
                    "volumes": [100.0],
                    "as_of": "2026-08-05",
                }
            },
        ),
        patch.object(
            strategy_board,
            "_compute_snapshot",
            return_value={
                "signal": "buy",
                "signal_label": "买入",
                "strength": 1.2,
                "strength_tier": "mid",
                "strength_tier_label": "中",
                "reason_summary": "测试信号",
                "as_of": "2026-08-05",
                "last_close": 1800.0,
            },
        ),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy.strategy_board.load_trading_risk_prefs",
            return_value=_risk_prefs(),
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")

    assert out["source"] == "live"
    assert out["as_of"] == "2026-08-05"
    assert len(out["signals"]) == 1
    row = out["signals"][0]
    assert row["vt_symbol"] == "600519.SSE"
    assert row["signal"] == "buy"
    assert row["name"] == "茅台"
    assert out["panel_symbols"] == ["600519.SSE"]


def test_load_strategy_board_risk_summary_with_positions() -> None:
    from app.services.strategy import strategy_board

    db = _mock_db()
    with (
        patch.object(
            strategy_board.repo.WatchlistItemRepository,
            "list_items",
            return_value=[
                SimpleNamespace(symbol="600519", exchange="SSE", name="茅台"),
            ],
        ),
        patch.object(
            strategy_board.positions_repo.PositionRepository,
            "list_positions",
            return_value=[
                SimpleNamespace(
                    symbol="000001",
                    exchange="SZSE",
                    cost_price=10.0,
                    volume=100,
                    buy_date="2020-01-01",
                    notes="",
                    source="manual",
                ),
                SimpleNamespace(
                    symbol="600519",
                    exchange="SSE",
                    cost_price=100.0,
                    volume=100,
                    buy_date="2020-01-01",
                    notes="",
                    source="manual",
                ),
            ],
        ),
        patch.object(strategy_board.signal_panel_repo.SignalPanelRepository, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_load_daily_bars_map", return_value={}),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy.strategy_board.load_trading_risk_prefs",
            return_value=_risk_prefs(),
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")

    by_vt = {p["vt_symbol"]: p for p in out["positions"]}
    assert by_vt["000001.SZSE"]["risk_tags"] == []
    assert by_vt["600519.SSE"]["risk_tags"] == []

    rs = out["risk_summary"]
    assert rs["total_capital"] is None
    assert rs["actual_position_pct"] is None


def test_load_strategy_board_note_panel_no_signals() -> None:
    from app.services.strategy import strategy_board

    db = _mock_db()
    with (
        patch.object(strategy_board.repo.WatchlistItemRepository, "list_items", return_value=[]),
        patch.object(
            strategy_board.signal_panel_repo.SignalPanelRepository,
            "load_symbols",
            return_value=["600519.SSE"],
        ),
        patch.object(strategy_board, "_load_daily_bars_map", return_value={}),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy.strategy_board.load_trading_risk_prefs",
            return_value=_risk_prefs(),
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    assert out["panel_symbols"] == ["600519.SSE"]
    assert out["signals"] == []
    assert "warm_watchlist_strategy_cache" not in out["note"]
    assert "信号名单 1 只" in out["note"]
    assert "暂无信号" in out["note"]


def test_load_strategy_board_note_positions_no_signals() -> None:
    from app.services.strategy import strategy_board

    db = _mock_db()
    with (
        patch.object(strategy_board.repo.WatchlistItemRepository, "list_items", return_value=[]),
        patch.object(
            strategy_board.positions_repo.PositionRepository,
            "list_positions",
            return_value=[
                SimpleNamespace(
                    symbol="600519",
                    exchange="SSE",
                    cost_price=100.0,
                    volume=100,
                    buy_date="2026-01-01",
                    notes="",
                    source="manual",
                )
            ],
        ),
        patch.object(strategy_board.signal_panel_repo.SignalPanelRepository, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_load_daily_bars_map", return_value={}),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy.strategy_board.load_trading_risk_prefs",
            return_value=_risk_prefs(),
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    assert out["positions"]
    assert out["signals"] == []
    assert "warm_watchlist_strategy_cache" not in out["note"]
    assert "持仓来自记账表" in out["note"]


def test_note_empty_live_compute() -> None:
    from app.services.strategy import strategy_board

    db = _mock_db()
    with (
        patch.object(strategy_board.repo.WatchlistItemRepository, "list_items", return_value=[]),
        patch.object(strategy_board.signal_panel_repo.SignalPanelRepository, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_load_daily_bars_map", return_value={}),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy.strategy_board.load_trading_risk_prefs",
            return_value=_risk_prefs(),
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    note = out["note"]
    assert "warm_watchlist_strategy_cache" not in note
    assert "实时按日 K 计算" in note
    assert out["source"] == "live"
