from unittest.mock import MagicMock, patch

from app.services import ops_enrich_quotes as m


def test_enrich_skips_without_token() -> None:
    db = MagicMock()
    with patch(
        "app.services.ops_enrich_quotes.ts.require_token",
        side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
    ), patch("app.services.ops_enrich_quotes.save_job_run_meta") as save_meta:
        out = m.enrich_market_quotes(db)
    assert out["skipped"] is True
    assert "TUSHARE" in out["message"] or "未配置" in out["message"]
    save_meta.assert_called_once()


def test_enrich_skips_when_redis_unavailable() -> None:
    db = MagicMock()
    store = MagicMock()
    store.meta.return_value = {"available": False}
    with patch("app.services.ops_enrich_quotes.ts.require_token", return_value="tok"), patch(
        "app.services.ops_enrich_quotes.get_quote_store", return_value=store
    ), patch("app.services.ops_enrich_quotes.save_job_run_meta") as save_meta:
        out = m.enrich_market_quotes(db)
    assert out["skipped"] is True
    save_meta.assert_called_once()


def test_enrich_applies_patches_from_tushare() -> None:
    db = MagicMock()
    store = MagicMock()
    store.meta.return_value = {"available": True}
    client = MagicMock()
    basic = [
        {
            "ts_code": "600519.SH",
            "turnover_rate": 1.0,
            "volume_ratio": 2.0,
            "total_mv": 10,
            "circ_mv": 9,
        }
    ]
    flow = [{"ts_code": "600519.SH", "net_mf_amount": 5.0}]
    with patch("app.services.ops_enrich_quotes.ts.require_token", return_value="tok"), patch(
        "app.services.ops_enrich_quotes.get_quote_store", return_value=store
    ), patch("app.services.ops_enrich_quotes.latest_open_yyyymmdd", return_value="20260811"), patch(
        "app.services.ops_enrich_quotes.fetch_daily_basic_rows", return_value=basic
    ), patch(
        "app.services.ops_enrich_quotes.fetch_moneyflow_rows", return_value=flow
    ), patch(
        "app.services.ops_enrich_quotes.apply_factor_patches",
        return_value={"updated": 1, "seq": 7, "published": True},
    ) as ap, patch(
        "app.services.ops_enrich_quotes.save_job_run_meta"
    ), patch(
        "app.services.ops_enrich_quotes.redis.Redis.from_url", return_value=client
    ) as from_url:
        out = m.enrich_market_quotes(db)
    assert out["success"] is True
    assert out.get("skipped") is not True
    from_url.assert_called_once()
    assert ap.called
    assert ap.call_args.args[0] is client
    patches = ap.call_args.args[1]
    assert "SHSE.600519" in patches
    assert patches["SHSE.600519"]["volume_ratio"] == 2.0
    assert patches["SHSE.600519"]["net_mf_amount"] == 5.0
    client.close.assert_called_once()


def test_enrich_skips_when_tushare_empty() -> None:
    db = MagicMock()
    store = MagicMock()
    store.meta.return_value = {"available": True}
    with patch("app.services.ops_enrich_quotes.ts.require_token", return_value="tok"), patch(
        "app.services.ops_enrich_quotes.get_quote_store", return_value=store
    ), patch("app.services.ops_enrich_quotes.latest_open_yyyymmdd", return_value="20260811"), patch(
        "app.services.ops_enrich_quotes.fetch_daily_basic_rows", return_value=[]
    ), patch(
        "app.services.ops_enrich_quotes.fetch_moneyflow_rows", return_value=[]
    ), patch("app.services.ops_enrich_quotes.save_job_run_meta") as save_meta, patch(
        "app.services.ops_enrich_quotes.redis.Redis.from_url"
    ) as from_url:
        out = m.enrich_market_quotes(db)
    assert out["skipped"] is True
    assert "因子" in out["message"] or "Tushare" in out["message"]
    save_meta.assert_called_once()
    from_url.assert_not_called()


def test_enrich_skips_when_no_quote_keys() -> None:
    db = MagicMock()
    store = MagicMock()
    store.meta.return_value = {"available": True}
    client = MagicMock()
    basic = [{"ts_code": "600519.SH", "turnover_rate": 1.0, "volume_ratio": 2.0, "total_mv": 10, "circ_mv": 9}]
    with patch("app.services.ops_enrich_quotes.ts.require_token", return_value="tok"), patch(
        "app.services.ops_enrich_quotes.get_quote_store", return_value=store
    ), patch("app.services.ops_enrich_quotes.latest_open_yyyymmdd", return_value="20260811"), patch(
        "app.services.ops_enrich_quotes.fetch_daily_basic_rows", return_value=basic
    ), patch(
        "app.services.ops_enrich_quotes.fetch_moneyflow_rows", return_value=[]
    ), patch(
        "app.services.ops_enrich_quotes.apply_factor_patches",
        return_value={"updated": 0, "seq": None, "published": False},
    ), patch("app.services.ops_enrich_quotes.save_job_run_meta") as save_meta, patch(
        "app.services.ops_enrich_quotes.redis.Redis.from_url", return_value=client
    ):
        out = m.enrich_market_quotes(db)
    assert out["skipped"] is True
    assert "行情键" in out["message"] or "collector" in out["message"]
    save_meta.assert_called_once()
    client.close.assert_called_once()


def test_net_mf_fallback_from_buy_sell() -> None:
    item = {
        "net_mf_amount": 0,
        "buy_lg_amount": 10,
        "buy_elg_amount": 5,
        "sell_lg_amount": 3,
        "sell_elg_amount": 2,
    }
    assert m._net_mf(item) == 10.0
