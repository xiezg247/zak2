from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.strategy_board import (
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
    from app.services.strategy_board import resolve_board_config_key

    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    assert resolve_board_config_key(db, "u1", signal_mode="double_ma") == "double_ma:5:20"


def test_resolve_board_config_key_double_ma_from_pref() -> None:
    from app.services.strategy_board import resolve_board_config_key

    db = MagicMock()
    db.execute.return_value.scalar.return_value = {
        "class_name": "AshareShortBreakoutStrategy",
        "fast_window": 5,
        "slow_window": 10,
    }
    assert resolve_board_config_key(db, "u1", signal_mode="double_ma") == "double_ma:5:10"


def test_resolve_board_config_key_trend_ma_fixed() -> None:
    from app.services.strategy_board import resolve_board_config_key

    db = MagicMock()
    assert resolve_board_config_key(db, "u1", signal_mode="trend_ma") == "trend_ma:20:60"


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


def test_enrich_position_risk_off_plan() -> None:
    out = enrich_position_risk(
        {"exit_signal": "hold", "unrealized_pnl_pct": None},
        change_pct=None,
        volume_ratio=None,
        off_plan=True,
    )
    assert out["off_plan"] is True
    assert "计划外" in out["risk_tags"]
    assert out["risk_primary"] == "计划外"


def test_load_strategy_board_empty() -> None:
    from app.services import strategy_board

    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
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
    with (
        patch.object(strategy_board.repo, "list_items", return_value=[]),
        patch.object(strategy_board.signal_panel_repo, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_scan_signal_redis", return_value=[]),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy_board.load_trading_risk_prefs",
            return_value={
                "total_capital": None,
                "stop_loss_pct": 0.05,
                "caution_float_pct": -5.0,
                "realized_pnl_today": None,
            },
        ),
        patch(
            "app.services.strategy_board.load_active_plan_snapshot",
            return_value=None,
        ),
        patch(
            "app.services.strategy_board.latest_open_yyyymmdd",
            return_value="20260805",
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    assert out["config_key"] == DEFAULT_CONFIG_KEY
    assert out["signals"] == []
    assert out["positions"] == []
    assert out["panel_symbols"] == []
    assert out["note"]
    assert "桌面" not in out["note"]
    assert "warm_watchlist_strategy_cache" in out["note"] or "双均线" in out["note"]
    assert "尚未接入策略引擎预热" not in out["note"]
    rs = out["risk_summary"]
    assert rs["total_capital"] is None
    assert rs["actual_position_pct"] is None
    assert rs["plan_max_pct"] is None
    assert rs["off_plan_count"] == 0
    assert rs["off_plan_symbols"] == []
    assert rs["active_plan_date"] == ""
    assert rs["plan_symbols"] == []


def test_load_strategy_board_risk_summary_with_off_plan() -> None:
    from app.services import strategy_board

    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
        _ = params
        result = MagicMock()
        sql = str(stmt)
        if "user_preferences" in sql:
            result.scalar.return_value = None
        elif "watchlist_positions" in sql:
            result.mappings.return_value.all.return_value = [
                {
                    "symbol": "000001",
                    "exchange": "SZSE",
                    "cost_price": 10.0,
                    "volume": 100,
                    "buy_date": "2020-01-01",
                    "notes": "",
                    "source": "manual",
                    "plan_pct": None,
                    "sort_order": 0,
                },
                {
                    "symbol": "600519",
                    "exchange": "SSE",
                    "cost_price": 100.0,
                    "volume": 100,
                    "buy_date": "2020-01-01",
                    "notes": "",
                    "source": "manual",
                    "plan_pct": None,
                    "sort_order": 1,
                },
            ]
        else:
            result.mappings.return_value.all.return_value = []
            result.mappings.return_value.first.return_value = None
        return result

    db.execute.side_effect = _execute
    with (
        patch.object(
            strategy_board.repo,
            "list_items",
            return_value=[
                SimpleNamespace(symbol="600519", exchange="SSE", name="茅台"),
            ],
        ),
        patch.object(strategy_board.signal_panel_repo, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_scan_signal_redis", return_value=[]),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy_board.load_trading_risk_prefs",
            return_value={
                "total_capital": 100_000.0,
                "stop_loss_pct": 0.05,
                "caution_float_pct": -5.0,
                "realized_pnl_today": None,
            },
        ),
        patch(
            "app.services.strategy_board.load_active_plan_snapshot",
            return_value={
                "vt_symbols": {"600519.SSE", "300750.SZSE"},
                "ordered_vt_symbols": ["600519.SSE", "300750.SZSE"],
                "max_position_pct": 80.0,
                "trade_date": "2026-08-05",
            },
        ) as snap,
        patch(
            "app.services.strategy_board.latest_open_yyyymmdd",
            return_value="20260805",
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")

    snap.assert_called_once_with(db, "u1", "2026-08-05")
    by_vt = {p["vt_symbol"]: p for p in out["positions"]}
    assert by_vt["000001.SZSE"]["off_plan"] is True
    assert "计划外" in by_vt["000001.SZSE"]["risk_tags"]
    assert by_vt["600519.SSE"]["off_plan"] is False
    assert "计划外" not in by_vt["600519.SSE"]["risk_tags"]

    rs = out["risk_summary"]
    assert rs["total_capital"] == 100_000.0
    assert rs["actual_position_pct"] == 0.0  # 无行情 → market_value 计 0
    assert rs["plan_max_pct"] == 0.8
    assert rs["off_plan_count"] == 1
    assert rs["off_plan_symbols"] == ["000001.SZSE"]
    assert rs["active_plan_date"] == "2026-08-05"
    assert rs["plan_symbols"] == [
        {
            "vt_symbol": "600519.SSE",
            "name": "茅台",
            "in_watchlist": True,
            "in_position": True,
        },
        {
            "vt_symbol": "300750.SZSE",
            "name": "",
            "in_watchlist": False,
            "in_position": False,
        },
    ]


def test_load_strategy_board_note_panel_no_signals() -> None:
    from app.services import strategy_board

    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
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
    with (
        patch.object(strategy_board.repo, "list_items", return_value=[]),
        patch.object(
            strategy_board.signal_panel_repo,
            "load_symbols",
            return_value=["600519.SSE"],
        ),
        patch.object(strategy_board, "_scan_signal_redis", return_value=[]),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy_board.load_trading_risk_prefs",
            return_value={
                "total_capital": None,
                "stop_loss_pct": 0.05,
                "caution_float_pct": -5.0,
                "realized_pnl_today": None,
            },
        ),
        patch(
            "app.services.strategy_board.load_active_plan_snapshot",
            return_value=None,
        ),
        patch(
            "app.services.strategy_board.latest_open_yyyymmdd",
            return_value="20260805",
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    assert out["panel_symbols"] == ["600519.SSE"]
    assert out["signals"] == []
    assert "桌面" not in out["note"]
    assert "信号名单 1 只" in out["note"]
    assert "warm_watchlist_strategy_cache" in out["note"]
    assert "尚未接入策略引擎预热" not in out["note"]


def test_load_strategy_board_note_positions_no_signals() -> None:
    from app.services import strategy_board

    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
        _ = params
        result = MagicMock()
        sql = str(stmt)
        if "user_preferences" in sql:
            result.scalar.return_value = None
        elif "watchlist_positions" in sql:
            result.mappings.return_value.all.return_value = [
                {
                    "symbol": "600519",
                    "exchange": "SSE",
                    "cost_price": 100.0,
                    "volume": 100,
                    "buy_date": "2026-01-01",
                    "notes": "",
                    "source": "manual",
                    "plan_pct": None,
                    "sort_order": 0,
                }
            ]
            result.mappings.return_value.first.return_value = None
        else:
            result.mappings.return_value.all.return_value = []
            result.mappings.return_value.first.return_value = None
        return result

    db.execute.side_effect = _execute
    with (
        patch.object(strategy_board.repo, "list_items", return_value=[]),
        patch.object(strategy_board.signal_panel_repo, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_scan_signal_redis", return_value=[]),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy_board.load_trading_risk_prefs",
            return_value={
                "total_capital": None,
                "stop_loss_pct": 0.05,
                "caution_float_pct": -5.0,
                "realized_pnl_today": None,
            },
        ),
        patch(
            "app.services.strategy_board.load_active_plan_snapshot",
            return_value=None,
        ),
        patch(
            "app.services.strategy_board.latest_open_yyyymmdd",
            return_value="20260805",
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    assert out["positions"]
    assert out["signals"] == []
    assert "桌面" not in out["note"]
    assert "持仓来自记账表" in out["note"]
    assert "warm_watchlist_strategy_cache" in out["note"]
    assert "尚未接入策略引擎预热" not in out["note"]


def test_note_empty_mentions_heuristic_job() -> None:
    from app.services import strategy_board

    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
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
    with (
        patch.object(strategy_board.repo, "list_items", return_value=[]),
        patch.object(strategy_board.signal_panel_repo, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_scan_signal_redis", return_value=[]),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy_board.load_trading_risk_prefs",
            return_value={
                "total_capital": None,
                "stop_loss_pct": 0.05,
                "caution_float_pct": -5.0,
                "realized_pnl_today": None,
            },
        ),
        patch(
            "app.services.strategy_board.load_active_plan_snapshot",
            return_value=None,
        ),
        patch(
            "app.services.strategy_board.latest_open_yyyymmdd",
            return_value="20260805",
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    note = out["note"]
    assert "warm_watchlist_strategy_cache" in note or "双均线" in note
    assert "尚未接入策略引擎预热" not in note
    assert "桌面" not in note