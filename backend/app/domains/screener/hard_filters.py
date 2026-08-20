"""硬过滤模板与应用。"""

from __future__ import annotations

from app.domains.screener.schemas import HardFilterPrefs, HardFilterTemplate
from app.services.market.quotes import QuoteRow, _to_vt_symbol

TEMPLATES: list[HardFilterTemplate] = [
    HardFilterTemplate(
        id="conservative",
        name="保守",
        prefs=HardFilterPrefs(
            exclude_st=True,
            exclude_suspended=True,
            min_amount_wan=5000.0,
            min_total_mv_yi=100.0,
            exclude_new_listing=True,
            min_listing_days=60,
            exclude_limit_board=True,
        ),
    ),
    HardFilterTemplate(
        id="balanced",
        name="均衡",
        prefs=HardFilterPrefs(
            exclude_st=True,
            exclude_suspended=True,
            min_amount_wan=3000.0,
            min_total_mv_yi=50.0,
            exclude_new_listing=False,
            min_listing_days=60,
            exclude_limit_board=False,
        ),
    ),
    HardFilterTemplate(
        id="aggressive",
        name="激进",
        prefs=HardFilterPrefs(
            exclude_st=True,
            exclude_suspended=True,
            min_amount_wan=500.0,
            min_total_mv_yi=20.0,
            exclude_new_listing=False,
            min_listing_days=60,
            exclude_limit_board=False,
        ),
    ),
]

_TEMPLATE_MAP = {item.id: item for item in TEMPLATES}


def resolve_hard_filter(
    prefs: HardFilterPrefs | None = None,
    template_id: str | None = None,
) -> HardFilterPrefs:
    tmpl = _TEMPLATE_MAP.get(template_id) if template_id else None
    if prefs is None and tmpl is None:
        return _TEMPLATE_MAP["balanced"].prefs.model_copy()
    if prefs is None:
        return tmpl.prefs.model_copy()  # type: ignore[union-attr]
    if tmpl is None:
        return prefs
    base = tmpl.prefs.model_copy()
    for key, val in prefs.model_dump(exclude_unset=True).items():
        setattr(base, key, val)
    return base


def _market_board(tf_symbol: str) -> str:
    """SHSE.600519 → 主板/科创等粗分：用交易所前缀近似。"""
    if "." not in tf_symbol:
        return ""
    exch = tf_symbol.split(".", 1)[0].upper()
    code = tf_symbol.split(".", 1)[1]
    if exch == "BJSE":
        return "北交所"
    if exch == "SHSE":
        if code.startswith("688"):
            return "科创板"
        return "沪市"
    if exch == "SZSE":
        if code.startswith(("300", "301")):
            return "创业板"
        return "深市"
    return exch


def apply_hard_filters(
    rows: list[QuoteRow],
    prefs: HardFilterPrefs,
    *,
    suspended_vts: set[str] | None = None,
) -> list[QuoteRow]:
    out: list[QuoteRow] = []
    min_amount_yuan = max(0.0, prefs.min_amount_wan) * 10_000.0
    min_mv_wan = max(0.0, prefs.min_total_mv_yi) * 10_000.0  # 亿 → 万
    allowed_industries = {x.strip() for x in prefs.allowed_industries.split(",") if x.strip()}
    allowed_boards = {x.strip() for x in prefs.allowed_market_boards.split(",") if x.strip()}

    for row in rows:
        name = row.name or ""
        if prefs.exclude_st and ("ST" in name.upper() or "退" in name):
            continue
        if prefs.exclude_one_word and row.amplitude > 0 and row.amplitude < 0.5 and abs(row.change_pct) >= 9.5:
            continue
        if prefs.exclude_limit_board and row.limit_times >= 2:
            continue
        # 成交额：有值才过滤（缺行情字段时不误杀）
        if min_amount_yuan > 0 and row.amount > 0 and row.amount < min_amount_yuan:
            continue
        # 总市值（万元）：有值才过滤
        mv = row.total_mv or row.circ_mv
        if min_mv_wan > 0 and mv > 0 and mv < min_mv_wan:
            continue
        if allowed_industries and row.industry and row.industry not in allowed_industries:
            continue
        if allowed_boards:
            board = _market_board(row.symbol)
            if board and board not in allowed_boards:
                continue
        # exclude_suspended：依赖 suspended_vts；空集/None 时不误杀
        if prefs.exclude_suspended and suspended_vts:
            vt = _to_vt_symbol(row.symbol)
            if vt in suspended_vts:
                continue
        # exclude_new_listing：Redis 快照通常无上市日，缺字段时跳过
        out.append(row)
    return out
