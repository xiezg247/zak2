"""默认 cron 配置与解析（供 embedded scheduler 使用）。"""

from __future__ import annotations

DEFAULT_CRON: dict[str, dict] = {
    "sync_universe": {"hour": 8, "minute": 0, "day_of_week": "mon"},
    "sync_stock_industry": {"hour": 8, "minute": 15, "day_of_week": "mon"},
    "sync_trade_calendar": {"hour": 7, "minute": 50, "day_of_week": "mon"},
    "sync_sector_flow_daily": {"hour": 17, "minute": 45, "day_of_week": "mon-fri"},
    "sync_limit_list": {"hour": 17, "minute": 50, "day_of_week": "mon-fri"},
    "screen_post_close": {"hour": 18, "minute": 0, "day_of_week": "mon-fri"},
    "fill_watchlist_bars": {"hour": 18, "minute": 0, "day_of_week": "mon-fri"},
    "batch_fill_stale": {"hour": 18, "minute": 30, "day_of_week": "mon-fri"},
    "batch_download_universe": {"hour": 16, "minute": 20, "day_of_week": "mon-fri"},
    "purge_stale_cache": {"hour": 19, "minute": 15, "day_of_week": "mon-fri"},
    "warm_market_summary": {"hour": 9, "minute": 25, "day_of_week": "mon-fri"},
    "screen_intraday": {
        "hours": [10, 14],
        "minute": 2,
        "day_of_week": "mon-fri",
    },
    "sync_bilibili_feed": {
        "hours": list(range(8, 20)),
        "minute": 15,
        "day_of_week": "mon-fri",
    },
    "enrich_market_quotes": {"hour": 15, "minute": 20, "day_of_week": "mon-fri"},
    "sync_suspend_daily": {"hour": 17, "minute": 40, "day_of_week": "mon-fri"},
    "sync_disclosure_calendar": {"hour": 8, "minute": 30, "day_of_week": "mon"},
    "prefetch_tushare": {"hour": 15, "minute": 30, "day_of_week": "mon-fri"},
    "prefetch_moneyflow": {"hour": 15, "minute": 35, "day_of_week": "mon-fri"},
    "sync_watchlist_financials": {"hour": 9, "minute": 0, "day_of_week": "mon"},
    "warm_radar_card_snapshots": {
        "hours": [9, 10, 14],
        "minute": 20,
        "day_of_week": "mon-fri",
    },
    "scan_horizon_outlook": {"hour": 18, "minute": 15, "day_of_week": "mon-fri"},
    "warm_watchlist_strategy_cache": {"hour": 18, "minute": 45, "day_of_week": "mon-fri"},
}

_FALLBACK = {"hour": 8, "minute": 0, "day_of_week": "mon-fri", "hours": None}


def _clamp_hour(value: int) -> int:
    return max(0, min(23, value))


def _clamp_minute(value: int) -> int:
    return max(0, min(59, value))


def _parse_hours(raw: str) -> list[int]:
    return [_clamp_hour(int(part.strip())) for part in raw.split(",") if part.strip()]


def resolve_cron(job_id: str, job_cfg: dict) -> dict:
    """解析 job 的 cron 参数，返回 hour/minute/day_of_week/hours。"""
    if job_id == "screen_intraday":
        defaults = DEFAULT_CRON["screen_intraday"]
        hours_raw = job_cfg.get("cron_hours")
        if hours_raw is not None and str(hours_raw).strip():
            hours = _parse_hours(str(hours_raw))
        else:
            hours = list(defaults["hours"])
        minute_raw = job_cfg.get("cron_minute_intraday")
        minute = _clamp_minute(int(minute_raw)) if minute_raw is not None else defaults["minute"]
        day_of_week = str(job_cfg.get("cron_day_of_week") or defaults["day_of_week"])
        return {
            "hour": hours[0] if hours else 0,
            "minute": minute,
            "day_of_week": day_of_week,
            "hours": hours,
        }

    if job_id not in DEFAULT_CRON:
        hour = job_cfg.get("cron_hour", _FALLBACK["hour"])
        minute = job_cfg.get("cron_minute", _FALLBACK["minute"])
        day_of_week = str(job_cfg.get("cron_day_of_week") or _FALLBACK["day_of_week"])
        return {
            "hour": _clamp_hour(int(hour)),
            "minute": _clamp_minute(int(minute)),
            "day_of_week": day_of_week,
            "hours": None,
        }

    defaults = DEFAULT_CRON[job_id]
    minute_raw = job_cfg.get("cron_minute", defaults.get("minute", _FALLBACK["minute"]))
    minute = _clamp_minute(int(minute_raw))
    day_of_week = str(job_cfg.get("cron_day_of_week") or defaults.get("day_of_week", _FALLBACK["day_of_week"]))

    default_hours = defaults.get("hours")
    if default_hours is not None:
        hours_raw = job_cfg.get("cron_hours")
        if hours_raw is not None and str(hours_raw).strip():
            hours = _parse_hours(str(hours_raw))
        else:
            hours = list(default_hours)
        return {
            "hour": hours[0] if hours else 0,
            "minute": minute,
            "day_of_week": day_of_week,
            "hours": hours,
        }

    hour = job_cfg.get("cron_hour", defaults.get("hour", _FALLBACK["hour"]))
    return {
        "hour": _clamp_hour(int(hour)),
        "minute": minute,
        "day_of_week": day_of_week,
        "hours": None,
    }
