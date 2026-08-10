from __future__ import annotations

from typing import Any

from app.services import ai_read_tools


def run(ctx: Any, args: dict[str, Any]) -> Any:
    args = args or {}
    if str(args.get("vt_symbol") or args.get("symbol") or "").strip():
        return ai_read_tools.get_stock_notes(ctx.db, ctx.user_id, args)
    return ai_read_tools.list_note_symbols(ctx.db, ctx.user_id, args)
