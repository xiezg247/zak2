from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.schemas.watchlist import TradingRiskPrefsOut
from app.services.ai import ai_read_tools as art
from app.services.ai.ai_tools import WRITE_TOOL_NAMES, execute_tool


def test_get_market_emotion_shape() -> None:
    db = MagicMock()
    with (
        patch.object(art.market, "load_emotion", return_value={"phase": "冰点"}),
        patch.object(art.market, "market_overview", return_value={"ok": 1}),
    ):
        out = art.get_market_emotion(db, "u", {})
    assert out["emotion"]["phase"] == "冰点"
    assert out["overview"] == {"ok": 1}


def test_ai_tools_delegates_emotion() -> None:
    with patch("app.services.ai.ai_read_tools.get_market_emotion", return_value={"emotion": {}, "overview": {}}) as m:
        raw = execute_tool(MagicMock(), "u", "get_market_emotion", {})
    assert "emotion" in raw
    m.assert_called_once()


def test_ai_tools_delegates_get_positions() -> None:
    with patch("app.services.ai.ai_read_tools.get_positions", return_value={"count": 0, "items": []}) as m:
        raw = execute_tool(MagicMock(), "u", "get_positions", {"limit": 5})
    assert "count" in raw
    m.assert_called_once()


def test_run_skill_watchlist_mocked() -> None:
    with patch("app.services.ai.ai_read_tools.get_watchlist", return_value={"count": 0, "items": []}) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "watchlist", "limit": 5})
    assert "items" in out or "count" in out
    m.assert_called_once()


def test_run_skill_screener_mocked() -> None:
    with patch("app.services.ai.ai_read_tools.get_recent_screening", return_value={"runs": []}) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "screener", "limit": 2})
    assert "runs" in out
    m.assert_called_once()


def test_run_skill_radar_mocked() -> None:
    with patch("app.services.ai.ai_read_tools.get_radar_snapshot", return_value={"cards": []}) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "radar"})
    assert "cards" in out
    m.assert_called_once()


def test_list_note_symbols_limit() -> None:
    items = [
        SimpleNamespace(model_dump=lambda i=i: {"vt_symbol": f"{i}.SSE", "memo_preview": "", "entry_count": 0})
        for i in range(5)
    ]
    with patch.object(art, "notes") as n:
        n.list_note_symbols.return_value = items
        out = art.list_note_symbols(MagicMock(), "u", {"limit": 2})
    assert out["count"] == 2
    assert len(out["symbols"]) == 2


def test_get_stock_notes_requires_symbol() -> None:
    out = art.get_stock_notes(MagicMock(), "u", {})
    assert "error" in out


def test_get_stock_notes_ok() -> None:
    memo = SimpleNamespace(model_dump=lambda: {"vt_symbol": "600519.SSE", "body": "x"})
    entries = [SimpleNamespace(model_dump=lambda: {"id": 1, "body": "e"})]
    with patch.object(art, "notes") as n:
        n.get_memo.return_value = memo
        n.list_entries.return_value = entries
        out = art.get_stock_notes(MagicMock(), "u", {"vt_symbol": "600519.SSE", "entry_limit": 10})
    assert out["memo"]["body"] == "x"
    assert out["entry_count"] == 1
    n.list_entries.assert_called_once()


def test_run_skill_notes_list() -> None:
    assert "list_note_symbols" not in WRITE_TOOL_NAMES
    assert "get_stock_notes" not in WRITE_TOOL_NAMES
    with patch("app.services.ai.ai_read_tools.list_note_symbols", return_value={"count": 0, "symbols": []}) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "notes"})
    assert "symbols" in out or "count" in out
    m.assert_called_once()


def test_run_skill_notes_stock() -> None:
    with patch(
        "app.services.ai.ai_read_tools.get_stock_notes",
        return_value={"memo": {}, "entries": [], "entry_count": 0},
    ) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "notes", "vt_symbol": "600519.SSE"})
    assert "memo" in out
    m.assert_called_once()


def test_get_positions_limit_and_shape() -> None:
    rows = [
        {
            "symbol": "600519",
            "exchange": "SSE",
            "vt_symbol": "600519.SSE",
            "cost_price": 100.0,
            "volume": 100,
            "buy_date": "2026-08-01",
            "notes": "",
            "source": "manual",
            "plan_pct": None,
            "sort_order": 0,
            "created_at": "",
            "updated_at": "",
        },
        {
            "symbol": "000001",
            "exchange": "SZSE",
            "vt_symbol": "000001.SZSE",
            "cost_price": 10.0,
            "volume": 200,
            "buy_date": "2026-07-01",
            "notes": "",
            "source": "manual",
            "plan_pct": 0.1,
            "sort_order": 1,
            "created_at": "",
            "updated_at": "",
        },
    ]
    with (
        patch("app.repositories.positions.PositionRepository.list_positions", return_value=rows) as lp,
        patch.object(art, "get_quote_store") as gq,
    ):
        store = MagicMock()
        store.get_quotes.return_value = []
        gq.return_value = store
        out = art.get_positions(MagicMock(), "u", {"limit": 1, "with_quotes": True})
    assert out["count"] == 1
    assert out["items"][0]["vt_symbol"] == "600519.SSE"
    lp.assert_called_once()


def test_get_positions_empty_and_skip_quotes() -> None:
    with (
        patch("app.repositories.positions.PositionRepository.list_positions", return_value=[]),
        patch.object(art, "get_quote_store") as gq,
    ):
        out = art.get_positions(MagicMock(), "u", {"with_quotes": True})
    assert out == {"count": 0, "items": []}
    gq.assert_not_called()


def test_get_positions_with_quotes_false_skips_store() -> None:
    rows = [
        {
            "symbol": "600519",
            "exchange": "SSE",
            "vt_symbol": "600519.SSE",
            "cost_price": 100.0,
            "volume": 100,
            "buy_date": "2026-08-01",
            "notes": "",
            "source": "manual",
            "plan_pct": None,
            "sort_order": 0,
            "created_at": "",
            "updated_at": "",
        }
    ]
    with (
        patch("app.repositories.positions.PositionRepository.list_positions", return_value=rows),
        patch.object(art, "get_quote_store") as gq,
    ):
        out = art.get_positions(MagicMock(), "u", {"with_quotes": False})
    assert out["count"] == 1
    assert "last_price" not in out["items"][0]
    gq.assert_not_called()


def test_get_positions_quote_store_failure_still_returns() -> None:
    rows = [
        {
            "symbol": "600519",
            "exchange": "SSE",
            "vt_symbol": "600519.SSE",
            "cost_price": 100.0,
            "volume": 100,
            "buy_date": "2026-08-01",
            "notes": "",
            "source": "manual",
            "plan_pct": None,
            "sort_order": 0,
            "created_at": "",
            "updated_at": "",
        }
    ]
    with (
        patch("app.repositories.positions.PositionRepository.list_positions", return_value=rows),
        patch.object(art, "get_quote_store", side_effect=RuntimeError("redis down")),
    ):
        out = art.get_positions(MagicMock(), "u", {"with_quotes": True})
    assert out["count"] == 1
    assert out["items"][0]["vt_symbol"] == "600519.SSE"


def test_get_signal_panel_delegates() -> None:
    payload = {"symbols": ["600519.SSE"], "count": 1, "max_symbols": 10}
    with patch("app.repositories.signal_panel.SignalPanelRepository.panel_payload", return_value=payload) as pp:
        out = art.get_signal_panel(MagicMock(), "u", {})
    assert out == payload
    pp.assert_called_once()


def test_run_skill_positions_all() -> None:
    assert "get_positions" not in WRITE_TOOL_NAMES
    with (
        patch("app.services.ai.ai_read_tools.get_positions", return_value={"count": 0, "items": []}) as gp,
        patch(
            "app.services.ai.ai_read_tools.get_signal_panel",
            return_value={"symbols": [], "count": 0, "max_symbols": 10},
        ) as gs,
        patch(
            "app.services.ai.ai_read_tools.get_trading_risk",
            return_value={"prefs": {}, "risk_summary": {}},
        ) as gr,
    ):
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "positions"})
    assert "positions" in out and "signal_panel" in out and "trading_risk" in out
    gp.assert_called_once()
    gs.assert_called_once()
    gr.assert_called_once()


def test_run_skill_positions_section_signals() -> None:
    with patch(
        "app.services.ai.ai_read_tools.get_signal_panel",
        return_value={"symbols": ["600519.SSE"], "count": 1, "max_symbols": 10},
    ) as gs:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "positions", "section": "signals"})
    assert "600519" in out or "symbols" in out
    gs.assert_called_once()


def test_get_trading_risk_prefs_and_summary() -> None:
    prefs = TradingRiskPrefsOut(
        total_capital=100000.0,
        stop_loss_pct=0.05,
        caution_float_pct=-5.0,
        realized_pnl_today=None,
    )
    board = {
        "risk_summary": {
            "total_capital": 100000.0,
            "actual_position_pct": 0.2,
            "plan_max_pct": 0.5,
            "off_plan_count": 0,
            "off_plan_symbols": [],
            "active_plan_date": "2026-08-11",
            "plan_symbols": [
                {"vt_symbol": "600519.SSE", "status": "in_position", "name": "茅台", "extra": "drop_me"},
            ],
        }
    }
    with (
        patch.object(art, "trading_risk") as tr,
        patch.object(art, "strategy_board") as sb,
    ):
        tr.load_trading_risk_prefs.return_value = prefs
        sb.load_strategy_board.return_value = board
        out = art.get_trading_risk(MagicMock(), "u", {})
    assert out["prefs"]["total_capital"] == 100000.0
    assert out["risk_summary"]["actual_position_pct"] == 0.2
    assert out["risk_summary"]["plan_symbols"] == [{"vt_symbol": "600519.SSE", "status": "in_position"}]
