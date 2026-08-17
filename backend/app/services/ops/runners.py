"""运维任务 runner 映射（与 ops_catalog.RUNNABLE_JOB_IDS 对齐）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.services.ops import (
    auto_screen as ops_auto_screen,
)
from app.services.ops import (
    bars_fill as ops_bars_fill,
)
from app.services.ops import (
    enrich_quotes as ops_enrich_quotes,
)
from app.services.ops import (
    fill_focus_pool_minute as ops_fill_focus_pool_minute,
)
from app.services.ops import (
    prefetch_concept_board as ops_prefetch_concept_board,
)
from app.services.ops import (
    prefetch_moneyflow as ops_prefetch_moneyflow,
)
from app.services.ops import (
    prefetch_tushare as ops_prefetch_tushare,
)
from app.services.ops import (
    purge as ops_purge,
)
from app.services.ops import (
    scan_horizon_outlook as ops_scan_horizon_outlook,
)
from app.services.ops import (
    sync_bilibili_feed as ops_sync_bilibili_feed,
)
from app.services.ops import (
    sync_calendar as ops_sync_calendar,
)
from app.services.ops import (
    sync_disclosure as ops_sync_disclosure,
)
from app.services.ops import (
    sync_limit_list as ops_sync_limit_list,
)
from app.services.ops import (
    sync_sector as ops_sync_sector,
)
from app.services.ops import (
    sync_stock_industry as ops_sync_stock_industry,
)
from app.services.ops import (
    sync_suspend as ops_sync_suspend,
)
from app.services.ops import (
    sync_universe as ops_sync_universe,
)
from app.services.ops import (
    sync_watchlist_financials as ops_sync_watchlist_financials,
)
from app.services.ops import (
    warm_market as ops_warm_market,
)
from app.services.ops import (
    warm_radar as ops_warm_radar,
)
from app.services.ops import (
    warm_watchlist_strategy as ops_warm_watchlist_strategy,
)

SCREEN_JOB_IDS = frozenset({"screen_intraday", "screen_post_close"})


def _run_sync_bilibili_feed(db: Session, **_kwargs: Any) -> dict:
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
    "prefetch_concept_board": ops_prefetch_concept_board.prefetch_concept_board,
    "fill_focus_pool_minute": ops_fill_focus_pool_minute.fill_focus_pool_minute,
}


def needs_user_id(job_id: str) -> bool:
    return job_id in SCREEN_JOB_IDS
