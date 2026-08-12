from unittest.mock import MagicMock, patch

from app.services.ops_scheduler import job_kind_for, list_scheduler_jobs


def test_job_kind_mapping() -> None:
    assert job_kind_for("purge_stale_cache") == "runnable"
    assert job_kind_for("collect_quotes") == "process"
    assert job_kind_for("enrich_market_quotes") == "runnable"
    assert job_kind_for("sync_suspend_daily") == "runnable"
    assert job_kind_for("sync_disclosure_calendar") == "runnable"
    assert job_kind_for("prefetch_tushare") == "runnable"
    assert job_kind_for("warm_radar_card_snapshots") == "runnable"
    assert job_kind_for("prefetch_moneyflow") == "runnable"
    assert job_kind_for("sync_watchlist_financials") == "runnable"
    assert job_kind_for("warm_watchlist_strategy_cache") == "runnable"
    assert job_kind_for("scan_horizon_outlook") == "runnable"
    assert job_kind_for("prefetch_concept_board") == "planned"


def test_list_jobs_includes_job_kind() -> None:
    db = MagicMock()
    with patch("app.services.ops_scheduler.load_scheduler_config", return_value={"config": {}}), patch(
        "app.services.ops_scheduler.load_job_run_meta", return_value=None
    ):
        rows = {r["job_id"]: r for r in list_scheduler_jobs(db)}
    assert rows["collect_quotes"]["job_kind"] == "process"
    assert rows["purge_stale_cache"]["job_kind"] == "runnable"
    assert rows["enrich_market_quotes"]["job_kind"] == "runnable"
    assert rows["sync_suspend_daily"]["job_kind"] == "runnable"
    assert rows["prefetch_moneyflow"]["job_kind"] == "runnable"
    assert rows["sync_watchlist_financials"]["job_kind"] == "runnable"
    assert rows["prefetch_concept_board"]["job_kind"] == "planned"
