from __future__ import annotations

from typing import Any

from app.services.ai import ai_read_tools


def run(ctx: Any, args: dict[str, Any]) -> Any:
    return ai_read_tools.get_radar_snapshot(ctx.db, ctx.user_id, args or {})
