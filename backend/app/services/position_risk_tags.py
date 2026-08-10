FLOAT_LOSS_PCT = -5.0
FLOAT_GAIN_PCT = 15.0
INTRADAY_DROP_PCT = -3.0
INTRADAY_SURGE_PCT = 5.0
VOLUME_RATIO_ACTIVE = 1.2
VOLUME_CHANGE_ABS_MIN = 1.5
TAG_ORDER: tuple[str, ...] = ("卖出信号", "计划外", "急跌", "浮亏", "放量", "大涨", "浮盈")


def compute_position_risk_tags(
    *,
    exit_signal: str | None,
    unrealized_pnl_pct: float | None,
    change_pct: float | None,
    volume_ratio: float | None,
    off_plan: bool = False,
) -> list[str]:
    hit: set[str] = set()
    if (exit_signal or "").strip().lower() == "sell":
        hit.add("卖出信号")
    if off_plan:
        hit.add("计划外")
    if change_pct is not None:
        cp = float(change_pct)
        if cp <= INTRADAY_DROP_PCT:
            hit.add("急跌")
        elif cp >= INTRADAY_SURGE_PCT:
            hit.add("大涨")
        if (
            volume_ratio is not None
            and float(volume_ratio) >= VOLUME_RATIO_ACTIVE
            and abs(cp) >= VOLUME_CHANGE_ABS_MIN
        ):
            hit.add("放量")
    if unrealized_pnl_pct is not None:
        pnl = float(unrealized_pnl_pct)
        if pnl <= FLOAT_LOSS_PCT:
            hit.add("浮亏")
        elif pnl >= FLOAT_GAIN_PCT:
            hit.add("浮盈")
    return [t for t in TAG_ORDER if t in hit]


def primary_risk_tag(tags: list[str]) -> str:
    return tags[0] if tags else ""
