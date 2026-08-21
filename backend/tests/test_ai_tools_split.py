"""ai_tools 拆分子包结构回归：子模块符号归属 + ai_tools 聚合全量。"""

from __future__ import annotations

from app.services.ai.tools._common import MAX_RESULT_CHARS, _parse_args, _truncate
from app.services.ai.tools.read import READ_DEFINITIONS, READ_HANDLERS
from app.services.ai.tools.skills import SKILL_DEFINITIONS, SKILL_HANDLERS
from app.services.ai.tools.write import (
    WRITE_DEFINITIONS,
    WRITE_HANDLERS,
    WRITE_TOOL_NAMES,
    summarize_write_tool,
)


def test_common_module_exports() -> None:
    assert MAX_RESULT_CHARS == 6000
    assert _parse_args(None) == {}
    assert _parse_args('{"a": 1}') == {"a": 1}
    assert callable(_truncate)


def test_read_module_registers_11() -> None:
    names = set(READ_HANDLERS)
    assert names == {
        "get_watchlist",
        "get_positions",
        "get_signal_panel",
        "get_trading_risk",
        "get_market_emotion",
        "get_recent_screening",
        "get_radar_snapshot",
        "list_note_symbols",
        "get_stock_notes",
        "get_bars_summary",
        "get_recent_backtest",
    }
    assert {d["function"]["name"] for d in READ_DEFINITIONS} == names


def test_skills_module_registers_3() -> None:
    assert set(SKILL_HANDLERS) == {"list_skills", "read_skill", "run_skill"}
    assert {d["function"]["name"] for d in SKILL_DEFINITIONS} == set(SKILL_HANDLERS)


def test_write_module_registers_8() -> None:
    assert set(WRITE_HANDLERS) == set(WRITE_TOOL_NAMES) == {
        "add_watchlist",
        "remove_watchlist",
        "upsert_note_memo",
        "add_note_entry",
        "upsert_position",
        "delete_position",
        "add_signal_panel",
        "remove_signal_panel",
    }
    assert {d["function"]["name"] for d in WRITE_DEFINITIONS} == set(WRITE_TOOL_NAMES)


def test_ai_tools_aggregates_all() -> None:
    from app.services.ai import ai_tools

    all_names = set(READ_HANDLERS) | set(SKILL_HANDLERS) | set(WRITE_HANDLERS)
    assert set(ai_tools.TOOL_HANDLERS) == all_names == {*WRITE_TOOL_NAMES, *ai_tools.TOOL_HANDLERS}
    assert {d["function"]["name"] for d in ai_tools.TOOL_DEFINITIONS} == all_names
