"""AI 持仓/信号写工具（mock repo，不打真库）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.services.ai_tools import execute_write_tool, summarize_write_tool


def test_summarize_new_write_tools() -> None:
    s = summarize_write_tool(
        "upsert_position",
        {"symbol": "600519.SSE", "cost_price": 100, "volume": 100, "buy_date": "2026-08-01"},
    )
    assert "持仓" in s and "600519" in s
    assert "删除持仓" in summarize_write_tool("delete_position", {"symbol": "600519.SSE"})
    assert "信号名单" in summarize_write_tool("add_signal_panel", {"symbol": "600519.SSE"})
    assert "移出信号名单" in summarize_write_tool("remove_signal_panel", {"symbol": "600519.SSE"})


def test_upsert_not_in_watchlist() -> None:
    db = MagicMock()
    with (
        patch("app.services.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
        patch("app.repositories.positions.PositionRepository.get_position", return_value=None),
        patch(
            "app.repositories.positions.PositionRepository.add_position",
            side_effect=HTTPException(status_code=400, detail="须先加入自选再录入持仓"),
        ),
    ):
        out = execute_write_tool(
            db,
            "u1",
            "upsert_position",
            {
                "symbol": "600519.SSE",
                "cost_price": 100,
                "volume": 100,
                "buy_date": "2026-08-01",
            },
        )
    assert isinstance(out, dict)
    assert "error" in out
    assert "自选" in str(out["error"])


def test_upsert_creates_when_missing() -> None:
    db = MagicMock()
    row = {
        "vt_symbol": "600519.SSE",
        "symbol": "600519",
        "exchange": "SSE",
        "cost_price": 100.0,
        "volume": 100,
        "buy_date": "2026-08-01",
    }
    with (
        patch("app.services.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
        patch("app.repositories.positions.PositionRepository.get_position", return_value=None),
        patch("app.repositories.positions.PositionRepository.add_position", return_value=row) as add,
        patch("app.repositories.positions.PositionRepository.update_position") as upd,
    ):
        out = execute_write_tool(
            db,
            "u1",
            "upsert_position",
            {
                "symbol": "600519.SSE",
                "cost_price": 100,
                "volume": 100,
                "buy_date": "2026-08-01",
            },
        )
    assert out.get("ok") is True
    assert out.get("action") == "created"
    add.assert_called_once()
    upd.assert_not_called()


def test_upsert_updates_when_exists() -> None:
    db = MagicMock()
    existing = {"vt_symbol": "600519.SSE", "symbol": "600519", "exchange": "SSE"}
    row = {**existing, "cost_price": 110.0, "volume": 200, "buy_date": "2026-08-01"}
    with (
        patch("app.services.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
        patch("app.repositories.positions.PositionRepository.get_position", return_value=existing),
        patch("app.repositories.positions.PositionRepository.update_position", return_value=row) as upd,
        patch("app.repositories.positions.PositionRepository.add_position") as add,
    ):
        out = execute_write_tool(
            db,
            "u1",
            "upsert_position",
            {
                "symbol": "600519.SSE",
                "cost_price": 110,
                "volume": 200,
                "buy_date": "2026-08-01",
            },
        )
    assert out.get("action") == "updated"
    upd.assert_called_once()
    add.assert_not_called()


def test_delete_position_missing() -> None:
    db = MagicMock()
    with (
        patch("app.services.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
        patch("app.repositories.positions.PositionRepository.delete_position", return_value=False),
    ):
        out = execute_write_tool(db, "u1", "delete_position", {"symbol": "600519.SSE"})
    assert "error" in out


def test_add_remove_signal_panel() -> None:
    db = MagicMock()
    with patch(
        "app.repositories.signal_panel.SignalPanelRepository.add_symbol",
        return_value=["600519.SSE"],
    ):
        out = execute_write_tool(db, "u1", "add_signal_panel", {"symbol": "600519.SSE"})
    assert out.get("ok") is True
    assert "600519.SSE" in (out.get("symbols") or [])

    with patch(
        "app.repositories.signal_panel.SignalPanelRepository.remove_symbol",
        side_effect=HTTPException(status_code=404, detail="不在信号名单中"),
    ):
        out2 = execute_write_tool(db, "u1", "remove_signal_panel", {"symbol": "600519.SSE"})
    assert "error" in out2
