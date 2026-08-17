from app.services.ops.catalog import RUNNABLE_JOB_IDS
from app.services.scheduler_defaults import resolve_cron


def test_defaults_cover_all_runnable() -> None:
    from app.services import scheduler_defaults as sd

    assert set(sd.DEFAULT_CRON) == set(RUNNABLE_JOB_IDS)


def test_resolve_stock_industry_monday() -> None:
    r = resolve_cron("sync_stock_industry", {})
    assert r["hour"] == 8 and r["minute"] == 15 and r["day_of_week"] == "mon"
    assert r["hours"] is None


def test_resolve_calendar_monday() -> None:
    r = resolve_cron("sync_trade_calendar", {})
    assert r["hour"] == 7 and r["minute"] == 50 and r["day_of_week"] == "mon"
    assert r["hours"] is None


def test_resolve_warm_market_summary() -> None:
    r = resolve_cron("warm_market_summary", {})
    assert r["hour"] == 9 and r["minute"] == 25 and r["day_of_week"] == "mon-fri"


def test_resolve_intraday_hours() -> None:
    r = resolve_cron("screen_intraday", {})
    assert r["hours"] == [10, 14]
    assert r["minute"] == 2
    r2 = resolve_cron("screen_intraday", {"cron_hours": "9,11,13", "cron_minute_intraday": 5})
    assert r2["hours"] == [9, 11, 13] and r2["minute"] == 5


def test_resolve_bilibili_feed_hours() -> None:
    r = resolve_cron("sync_bilibili_feed", {})
    assert r["hours"] == list(range(8, 20))
    assert r["minute"] == 15
    assert r["day_of_week"] == "mon-fri"
    r2 = resolve_cron("sync_bilibili_feed", {"cron_hours": "9,12,18", "cron_minute": 30})
    assert r2["hours"] == [9, 12, 18] and r2["minute"] == 30


def test_resolve_warm_radar_card_snapshots() -> None:
    r = resolve_cron("warm_radar_card_snapshots", {})
    assert r["hours"] == [9, 10, 14]
    assert r["minute"] == 20
    assert r["day_of_week"] == "mon-fri"


def test_resolve_sync_suspend_daily() -> None:
    r = resolve_cron("sync_suspend_daily", {})
    assert r["hour"] == 17 and r["minute"] == 40 and r["day_of_week"] == "mon-fri"
    assert r["hours"] is None


def test_resolve_prefetch_moneyflow() -> None:
    r = resolve_cron("prefetch_moneyflow", {})
    assert r["hour"] == 15 and r["minute"] == 35 and r["day_of_week"] == "mon-fri"
    assert r["hours"] is None


def test_resolve_sync_watchlist_financials() -> None:
    r = resolve_cron("sync_watchlist_financials", {})
    assert r["hour"] == 9 and r["minute"] == 0 and r["day_of_week"] == "mon"
    assert r["hours"] is None


def test_resolve_prefetch_concept_board() -> None:
    r = resolve_cron("prefetch_concept_board", {})
    assert r["hour"] == 17 and r["minute"] == 30 and r["day_of_week"] == "mon-fri"
    assert r["hours"] is None


def test_resolve_fill_focus_pool_minute() -> None:
    r = resolve_cron("fill_focus_pool_minute", {})
    assert r["hour"] == 19 and r["minute"] == 0 and r["day_of_week"] == "mon-fri"
    assert r["hours"] is None


def test_config_overrides_hour() -> None:
    r = resolve_cron("purge_stale_cache", {"cron_hour": 20, "cron_minute": 1})
    assert r["hour"] == 20 and r["minute"] == 1
