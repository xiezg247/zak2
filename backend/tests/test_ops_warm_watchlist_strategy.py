from unittest.mock import MagicMock, patch

from app.services import ops_warm_watchlist_strategy as m


def test_warm_bridges_redis_signals() -> None:
    db = MagicMock()
    fake_client = MagicMock()
    # scan yields one signal key; get returns envelope JSON
    signal_key = b"zak2:cache:signal:latest:AshareShortBreakoutStrategy:5:10:600519.SSE"
    fake_client.scan_iter.side_effect = lambda **kw: (
        iter([signal_key])
        if "signal:latest" in kw.get("match", "")
        else iter([])
    )
    fake_client.get.return_value = (
        b'{"payload":"{\\"signal\\":\\"buy\\",\\"vt_symbol\\":\\"600519.SSE\\"}",'
        b'"bar_as_of":"2026-08-12","updated_at":"2026-08-12T10:00:00+08:00"}'
    )
    with (
        patch.object(m, "_redis_client", return_value=fake_client),
        patch.object(m, "_list_config_keys", return_value=["AshareShortBreakoutStrategy:5:10"]),
        patch.object(m, "list_watchlist_symbols", return_value=[]),
        patch.object(m, "_upsert_signal") as up_sig,
        patch.object(m, "_upsert_position") as up_pos,
        patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta") as save,
    ):
        out = m.warm_watchlist_strategy_cache(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert out["written_signals"] == 1
    assert out["written_positions"] == 0
    up_sig.assert_called_once()
    up_pos.assert_not_called()
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_warm_empty_redis_still_success() -> None:
    db = MagicMock()
    with (
        patch.object(m, "_redis_client", return_value=None),
        patch.object(m, "_list_config_keys", return_value=["AshareShortBreakoutStrategy:5:10"]),
        patch.object(m, "list_watchlist_symbols", return_value=[]),
        patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta") as save,
    ):
        out = m.warm_watchlist_strategy_cache(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert out["written_signals"] == 0
    assert out["computed"] == 0
    assert "桥接" in out["message"] or "Redis" in out["message"] or "启发式" in out["message"]
    assert save.call_args.kwargs["last_success"] is True


def test_warm_computes_ma_signals() -> None:
    db = MagicMock()
    with (
        patch.object(m, "_redis_client", return_value=None),
        patch.object(m, "_list_config_keys", return_value=["AshareShortBreakoutStrategy:5:10"]),
        patch.object(m, "list_watchlist_symbols", return_value=[("600519", "SSE")]),
        patch.object(
            m,
            "_load_daily_closes",
            return_value=([10.0] * 20, [100.0] * 20, "2026-08-13"),
        ),
        patch.object(
            m,
            "compute_ma_signal",
            return_value={
                "signal": "hold",
                "signal_label": "观望",
                "vt_symbol": "600519.SSE",
                "as_of": "2026-08-13",
                "signal_date": "2026-08-13",
                "last_close": 10.0,
                "ma_gap_pct": 0.1,
                "reason_summary": "5/10 日均线持有/观望（启发式）",
                "strength": 0.1,
            },
        ) as comp,
        patch.object(m, "_upsert_signal") as up,
        patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta") as save,
    ):
        out = m.warm_watchlist_strategy_cache(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert out["computed"] == 1
    assert "双均线启发式" in out["message"]
    comp.assert_called()
    up.assert_called()
    assert save.call_args.kwargs["last_success"] is True


def test_warm_skips_missing_bars() -> None:
    db = MagicMock()
    with (
        patch.object(m, "_redis_client", return_value=None),
        patch.object(m, "_list_config_keys", return_value=["AshareShortBreakoutStrategy:5:10"]),
        patch.object(m, "list_watchlist_symbols", return_value=[("600519", "SSE")]),
        patch.object(m, "_load_daily_closes", return_value=None),
        patch.object(m, "_upsert_signal") as up,
        patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta"),
    ):
        out = m.warm_watchlist_strategy_cache(db)
    assert out["computed"] == 0
    assert out["skipped_bars"] >= 1
    up.assert_not_called()
