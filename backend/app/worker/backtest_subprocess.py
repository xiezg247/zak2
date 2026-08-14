"""子进程入口：stdin JSON → run_cta_backtest → stdout JSON。"""

from __future__ import annotations

import json
import sys
from typing import Any


def run_one_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.backtest_vnpy import run_cta_backtest

    return run_cta_backtest(
        list(payload["bar_records"]),
        vt_symbol=str(payload["vt_symbol"]),
        strategy_id=str(payload.get("strategy_id") or "double_ma"),
        setting=dict(payload.get("setting") or {}),
        start=str(payload["start"]),
        end=str(payload["end"]),
        capital=float(payload["capital"]),
        rate=float(payload["rate"]),
        slippage=float(payload["slippage"]),
        stamp_duty=float(payload["stamp_duty"]),
    )


def main() -> None:
    payload = json.load(sys.stdin)
    try:
        out = run_one_payload(payload)
        json.dump({"ok": True, "result": out}, sys.stdout)
    except Exception as exc:  # noqa: BLE001
        json.dump({"ok": False, "error": str(exc)}, sys.stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
