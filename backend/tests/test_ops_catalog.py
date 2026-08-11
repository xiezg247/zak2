from app.services.ops_catalog import JOB_SPECS, RUNNABLE_JOB_IDS
from app.services.ops_bars import bars_overview
from app.services.ops_runners import RUNNERS


def test_catalog_runnable_jobs() -> None:
    assert "purge_stale_cache" in RUNNABLE_JOB_IDS
    assert "sync_trade_calendar" in RUNNABLE_JOB_IDS
    assert "sync_sector_flow_daily" in RUNNABLE_JOB_IDS
    assert "sync_limit_list" in RUNNABLE_JOB_IDS
    assert "fill_watchlist_bars" in RUNNABLE_JOB_IDS
    assert "batch_fill_stale" in RUNNABLE_JOB_IDS
    assert "batch_download_universe" in RUNNABLE_JOB_IDS
    assert "sync_universe" in RUNNABLE_JOB_IDS
    assert "sync_stock_industry" in RUNNABLE_JOB_IDS
    assert "screen_intraday" in RUNNABLE_JOB_IDS
    assert "screen_post_close" in RUNNABLE_JOB_IDS
    assert "warm_market_summary" in RUNNABLE_JOB_IDS
    assert "sync_bilibili_feed" in RUNNABLE_JOB_IDS
    assert "enrich_market_quotes" in RUNNABLE_JOB_IDS
    assert "sync_suspend_daily" in RUNNABLE_JOB_IDS
    assert "sync_disclosure_calendar" in RUNNABLE_JOB_IDS
    assert "prefetch_tushare" in RUNNABLE_JOB_IDS
    assert "warm_radar_card_snapshots" in RUNNABLE_JOB_IDS
    ids = {s.job_id for s in JOB_SPECS}
    assert RUNNABLE_JOB_IDS <= ids


def test_runners_match_runnable() -> None:
    assert set(RUNNERS) == set(RUNNABLE_JOB_IDS)


def test_bars_overview_callable() -> None:
    assert callable(bars_overview)
