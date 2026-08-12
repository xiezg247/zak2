"""运维任务 runner 映射（与 ops_catalog.RUNNABLE_JOB_IDS 对齐）。"""

from __future__ import annotations

from typing import Callable

from app.services import (
    ops_auto_screen,
    ops_bars_fill,
    ops_enrich_quotes,
    ops_prefetch_moneyflow,
    ops_prefetch_tushare,
    ops_sync_watchlist_financials,
    ops_purge,
    ops_sync_bilibili_feed,
    ops_sync_calendar,
    ops_sync_disclosure,
    ops_sync_limit_list,
    ops_sync_sector,
    ops_sync_stock_industry,
    ops_sync_suspend,
    ops_sync_universe,
    ops_scan_horizon_outlook,
    ops_warm_market,
    ops_warm_radar,
    ops_warm_watchlist_strategy,
)

SCREEN_JOB_IDS = frozenset({"screen_intraday", "screen_post_close"})


def _run_sync_bilibili_feed(db, **_kwargs) -> dict:
    """Ops 手动跑：force=True，绕过时段窗口。定时走 embedded_scheduler（force=False）。"""
    return ops_sync_bilibili_feed.sync_bilibili_feed(db, force=True)


RUNNERS: dict[str, Callable[..., dict]] = {
    "purge_stale_cache": ops_purge.purge_stale_cache,
    "sync_trade_calendar": ops_sync_calendar.sync_trade_calendar,
    "sync_sector_flow_daily": ops_sync_sector.sync_sector_flow_daily,
    "sync_limit_list": ops_sync_limit_list.sync_limit_list,
    "fill_watchlist_bars": ops_bars_fill.fill_watchlist_bars,
    "batch_fill_stale": ops_bars_fill.batch_fill_stale,
    "batch_download_universe": ops_bars_fill.batch_download_universe,
    "sync_universe": ops_sync_universe.sync_universe,
    "sync_stock_industry": ops_sync_stock_industry.sync_stock_industry,
    "screen_intraday": ops_auto_screen.screen_intraday,
    "screen_post_close": ops_auto_screen.screen_post_close,
    "warm_market_summary": ops_warm_market.warm_market_summary,
    "sync_bilibili_feed": _run_sync_bilibili_feed,
    "enrich_market_quotes": ops_enrich_quotes.enrich_market_quotes,
    "sync_suspend_daily": ops_sync_suspend.sync_suspend_daily,
    "sync_disclosure_calendar": ops_sync_disclosure.sync_disclosure_calendar,
    "prefetch_tushare": ops_prefetch_tushare.prefetch_tushare,
    "prefetch_moneyflow": ops_prefetch_moneyflow.prefetch_moneyflow,
    "sync_watchlist_financials": ops_sync_watchlist_financials.sync_watchlist_financials,
    "warm_radar_card_snapshots": ops_warm_radar.warm_radar_card_snapshots,
    "warm_watchlist_strategy_cache": ops_warm_watchlist_strategy.warm_watchlist_strategy_cache,
    "scan_horizon_outlook": ops_scan_horizon_outlook.scan_horizon_outlook,
}


def needs_user_id(job_id: str) -> bool:
    return job_id in SCREEN_JOB_IDS
