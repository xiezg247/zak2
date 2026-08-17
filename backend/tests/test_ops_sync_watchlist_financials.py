from unittest.mock import MagicMock, patch

from app.services.ops import sync_watchlist_financials as m


def test_financials_skips_empty_watchlist() -> None:
    db = MagicMock()
    with (
        patch("app.services.ops.sync_watchlist_financials.ts.require_token", return_value="tok"),
        patch("app.services.ops.sync_watchlist_financials.list_watchlist_symbols", return_value=[]),
        patch("app.services.ops.sync_watchlist_financials.save_job_run_meta") as save,
    ):
        out = m.sync_watchlist_financials(db)
    assert out.skipped is True
    save.assert_called_once()


def test_financials_skips_without_token() -> None:
    db = MagicMock()
    with (
        patch(
            "app.services.ops.sync_watchlist_financials.ts.require_token",
            side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
        ),
        patch("app.services.ops.sync_watchlist_financials.save_job_run_meta") as save,
    ):
        out = m.sync_watchlist_financials(db)
    assert out.skipped is True
    assert out.success is False
    save.assert_called_once()


def test_financials_syncs_one_symbol() -> None:
    db = MagicMock()
    income = [
        {
            "end_date": "20251231",
            "ann_date": "20260401",
            "total_revenue": 100.0,
            "n_income_attr_p": 10.0,
            "operate_profit": 12.0,
            "basic_eps": 1.0,
        }
    ]
    balance = [
        {
            "end_date": "20251231",
            "ann_date": "20260401",
            "total_assets": 1000.0,
            "total_liab": 400.0,
            "total_hldr_eqy_exc_min_int": 600.0,
        }
    ]
    cashflow = [
        {
            "end_date": "20251231",
            "ann_date": "20260401",
            "n_cashflow_act": 20.0,
            "n_cashflow_inv_act": -5.0,
            "n_cash_flows_fnc_act": -3.0,
            "c_pay_acq_const_fiolta": 2.0,
        }
    ]

    def fake_query(api_name: str, params=None, *, fields: str = ""):
        return {"income": income, "balancesheet": balance, "cashflow": cashflow}[api_name]

    with (
        patch("app.services.ops.sync_watchlist_financials.ts.require_token", return_value="tok"),
        patch(
            "app.services.ops.sync_watchlist_financials.list_watchlist_symbols",
            return_value=[("000001", "SZSE")],
        ),
        patch("app.services.ops.sync_watchlist_financials.ts.query", side_effect=fake_query),
        patch("app.services.ops.sync_watchlist_financials.time.sleep"),
        patch("app.services.ops.sync_watchlist_financials.save_job_run_meta"),
    ):
        out = m.sync_watchlist_financials(db)
    assert out.success is True
    assert out.extra.get("ok", 0) == 1
    assert db.execute.called
    assert db.commit.called


def test_infer_period() -> None:
    assert m.infer_period("20250331") == "Q1"
    assert m.infer_period("20250630") == "H1"
    assert m.infer_period("20250930") == "Q3"
    assert m.infer_period("20251231") == "Annual"
