"""运维任务目录（与 zak JOB_SPECS 对齐；仅列出元数据）。"""

from __future__ import annotations

from dataclasses import dataclass

# zak2 可在 Web 内手动执行的 job
RUNNABLE_JOB_IDS = frozenset(
    {
        "purge_stale_cache",
        "sync_trade_calendar",
        "sync_sector_flow_daily",
        "sync_limit_list",
        "fill_watchlist_bars",
        "batch_fill_stale",
        "batch_download_universe",
        "sync_universe",
        "sync_stock_industry",
        "screen_intraday",
        "screen_post_close",
        "warm_market_summary",
        "sync_bilibili_feed",
        "enrich_market_quotes",
        "sync_suspend_daily",
        "sync_disclosure_calendar",
        "prefetch_tushare",
        "prefetch_moneyflow",
        "sync_watchlist_financials",
        "warm_radar_card_snapshots",
        "warm_watchlist_strategy_cache",
        "scan_horizon_outlook",
        "prefetch_concept_board",
        "fill_focus_pool_minute",
    }
)


@dataclass(frozen=True, slots=True)
class JobSpec:
    job_id: str
    name: str
    description: str
    config_attr: str


JOB_SPECS: tuple[JobSpec, ...] = (
    JobSpec("collect_quotes", "行情采集", "zak2 quote-collector → Redis（独立进程）", "collect_quotes"),
    JobSpec(
        "enrich_market_quotes",
        "行情因子 enrich",
        "Tushare daily_basic/moneyflow → Redis 因子字段（Web 可跑）",
        "enrich_market_quotes",
    ),
    JobSpec("sync_universe", "同步 A 股列表", "Tushare stock_basic → app.universe（Web 可跑）", "sync_universe"),
    JobSpec(
        "sync_stock_industry",
        "同步行业映射",
        "Tushare 申万 L2（失败回退 stock_basic）→ app.stock_industry（Web 可跑）",
        "sync_stock_industry",
    ),
    JobSpec("sync_trade_calendar", "同步交易日历", "Tushare → app.trade_calendar", "sync_trade_calendar"),
    JobSpec(
        "batch_download_universe",
        "全市场日 K",
        "全 A 日 K 首下/补起点（Web 可跑，单次上限）",
        "batch_download_universe",
    ),
    JobSpec(
        "prefetch_moneyflow",
        "主力资金预拉",
        "moneyflow → app.tushare_factor_cache（Web 可跑）",
        "prefetch_moneyflow",
    ),
    JobSpec(
        "sync_sector_flow_daily", "板块资金同步", "东财/同花顺板块资金 → sector_flow_daily", "sync_sector_flow_daily"
    ),
    JobSpec(
        "sync_limit_list", "涨停列表同步", "Tushare limit_list_d → limit_list_daily（封板时间）", "sync_limit_list"
    ),
    JobSpec(
        "sync_suspend_daily",
        "停牌日同步",
        "Tushare suspend_d → app.symbol_suspend_days（Web 可跑）",
        "sync_suspend_daily",
    ),
    JobSpec(
        "prefetch_tushare",
        "Tushare 因子预拉",
        "daily_basic/moneyflow → app.tushare_factor_cache（Web 可跑）",
        "prefetch_tushare",
    ),
    JobSpec(
        "prefetch_concept_board",
        "概念板块预拉",
        "复用 sync_sector_flow_daily 概念资金 → sector_flow_daily（Web 可跑）",
        "prefetch_concept_board",
    ),
    JobSpec("warm_market_summary", "市场摘要预热", "情绪周期预热写入短 TTL 缓存", "warm_market_summary"),
    JobSpec(
        "warm_watchlist_strategy_cache",
        "策略信号磁盘预热",
        "Redis 桥 + 日 K 启发式 v2 + double_ma + trend_ma 三轨 → watchlist_signal_cache（Web 可跑）",
        "warm_watchlist_strategy_cache",
    ),
    JobSpec(
        "sync_watchlist_financials",
        "同步自选财报",
        "自选 income/balancesheet/cashflow → financial_*（Web 可跑，近 2 年）",
        "sync_watchlist_financials",
    ),
    JobSpec(
        "sync_disclosure_calendar",
        "同步披露计划",
        "Tushare disclosure_date → app.disclosure_calendar（Web 可跑）",
        "sync_disclosure_calendar",
    ),
    JobSpec("fill_watchlist_bars", "补全自选日 K", "自选过期/缺失日 K → dbbardata", "fill_watchlist_bars"),
    JobSpec("batch_fill_stale", "补全过期日 K", "全市场 overview 过期日 K 增量补全（Web 可跑）", "batch_fill_stale"),
    JobSpec(
        "fill_focus_pool_minute",
        "关注池 1m K 补全",
        "自选关注池 1m K 增量下载 → dbbardata（Web 可跑）",
        "fill_focus_pool_minute",
    ),
    JobSpec("screen_intraday", "盘中自动选股", "盘中选股写历史", "screen_intraday"),
    JobSpec("screen_post_close", "盘后自动选股", "盘后选股写历史", "screen_post_close"),
    JobSpec(
        "scan_horizon_outlook",
        "雷达展望扫描",
        "共振启发式 + 规则预测 → horizon/predict cache（Web 可跑）",
        "scan_horizon_outlook",
    ),
    JobSpec(
        "warm_radar_card_snapshots",
        "雷达卡片预热",
        "合成卡片 → cache.radar_card_snapshot（Web 可跑）",
        "warm_radar_card_snapshots",
    ),
    JobSpec(
        "sync_bilibili_feed",
        "B站订阅同步",
        "B 站动态 → feed_items（Web 可跑；需 BILIBILI_COOKIES）",
        "sync_bilibili_feed",
    ),
    JobSpec(
        "purge_stale_cache",
        "清理过期缓存",
        "删除 cache schema 中过期 LLM/雷达 hint 与过旧策略缓存",
        "purge_stale_cache",
    ),
)

JOBS_BY_ID = {s.job_id: s for s in JOB_SPECS}
