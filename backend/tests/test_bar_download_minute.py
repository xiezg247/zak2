from datetime import datetime
from unittest.mock import MagicMock, patch

from app.domains.market import bar_download as bars


def test_fetch_minute_rows_calls_stk_mins() -> None:
    with patch.object(bars.ts, "query", return_value=[]) as q:
        bars.fetch_minute_rows(
            ts_code="600519.SH",
            start=datetime(2026, 8, 11, 9, 0, 0),
            end=datetime(2026, 8, 13, 19, 0, 0),
        )
    assert q.call_args.args[0] == "stk_mins"
    params = q.call_args.args[1]
    assert params["freq"] == "1min"
    assert "600519.SH" in params["ts_code"]
    assert "09:00:00" in params["start_date"]


def test_upsert_minute_bars_writes_and_refreshes() -> None:
    db = MagicMock()
    rows = [
        {
            "trade_time": "2026-08-13 09:31:00",
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.05,
            "vol": 100,
            "amount": 1000,
        }
    ]
    with patch.object(bars, "refresh_overview") as ref:
        n = bars.upsert_minute_bars(db, symbol="600519", exchange="SSE", rows=rows)
    assert n == 1
    assert db.execute.call_count >= 2  # delete + insert
    ref.assert_called_once()
    assert ref.call_args.kwargs.get("interval") == bars.INTERVAL_1M


def test_refresh_overview_accepts_interval() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.first.return_value = {
        "start_dt": datetime(2026, 8, 1),
        "end_dt": datetime(2026, 8, 13),
        "n": 10,
    }
    bars.refresh_overview(db, symbol="600519", exchange="SSE", interval="1m")
    # 至少一次 SQL 绑定含 interval 1m
    found = False
    for c in db.execute.call_args_list:
        params = c.args[1] if len(c.args) > 1 else c.kwargs.get("parameters") or {}
        if isinstance(params, dict) and params.get("iv") == "1m":
            found = True
            break
    assert found
