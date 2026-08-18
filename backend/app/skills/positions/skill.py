from __future__ import annotations

from typing import Any

from app.services.ai import ai_read_tools


def run(ctx: Any, args: dict[str, Any]) -> Any:
    args = args or {}
    section = str(args.get("section") or "all").strip().lower()
    if section in ("", "all"):
        return {
            "positions": ai_read_tools.get_positions(ctx.db, ctx.user_id, args),
            "signal_panel": ai_read_tools.get_signal_panel(ctx.db, ctx.user_id, args),
            "trading_risk": ai_read_tools.get_trading_risk(ctx.db, ctx.user_id, args),
        }
    if section in ("positions", "position"):
        return ai_read_tools.get_positions(ctx.db, ctx.user_id, args)
    if section in ("signals", "signal", "signal_panel"):
        return ai_read_tools.get_signal_panel(ctx.db, ctx.user_id, args)
    if section in ("risk", "trading_risk"):
        return ai_read_tools.get_trading_risk(ctx.db, ctx.user_id, args)
    return {"error": f"未知 section：{section}，可用 all|positions|signals|risk"}
