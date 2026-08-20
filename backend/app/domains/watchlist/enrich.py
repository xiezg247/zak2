"""自选条目行情 enrich（行业 / 停牌 / 稀疏字段）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domains.watchlist.schemas import WatchlistItemOut
from app.services.market.quotes import QuoteRow, get_quote_store
from app.services.market.stock_industry import enrich_rows_from_db
from app.services.market.suspend import load_suspended_vt_symbols
from app.services.symbols import to_tf_symbol, to_vt_symbol


def _opt_price(q: QuoteRow | None) -> float | None:
    if q is None or q.last_price <= 0:
        return None
    return float(q.last_price)


def _opt_field(q: QuoteRow | None, attr: str, *, positive: bool = False) -> float | None:
    """无行情或缺省 0（稀疏字段）时返回 None，避免前端展示假 0。"""
    if q is None:
        return None
    v = float(getattr(q, attr))
    if positive and v <= 0:
        return None
    return v


def enrich(items: list[Any], *, with_quotes: bool, db: Session | None = None) -> list[WatchlistItemOut]:
    suspended = load_suspended_vt_symbols(db) if db is not None else set()
    quote_map: dict[str, QuoteRow] = {}
    if with_quotes and items:
        store = get_quote_store()
        if store.available():
            tfs = [to_tf_symbol(i.symbol, i.exchange) for i in items]
            for quote in store.get_quotes(tfs):
                quote_map[quote.symbol] = quote

    rows: list[QuoteRow] = []
    if with_quotes and items:
        for item in items:
            tf = to_tf_symbol(item.symbol, item.exchange)
            q = quote_map.get(tf)
            rows.append(
                QuoteRow(
                    symbol=tf,
                    name=(q.name if q and q.name else item.name) or "",
                    last_price=q.last_price if q else 0.0,
                    change_pct=q.change_pct if q else 0.0,
                    turnover_rate=q.turnover_rate if q else 0.0,
                    volume=q.volume if q else 0.0,
                    amount=q.amount if q else 0.0,
                    volume_ratio=q.volume_ratio if q else 0.0,
                    industry=(q.industry if q else "") or "",
                )
            )
        enrich_rows_from_db(db, rows)

    industry_by_tf = {r.symbol: r.industry for r in rows}
    out: list[WatchlistItemOut] = []
    for item in items:
        tf = to_tf_symbol(item.symbol, item.exchange)
        vt = to_vt_symbol(item.symbol, item.exchange)
        q = quote_map.get(tf)
        name = item.name
        if q is not None and q.name:
            name = q.name
        out.append(
            WatchlistItemOut(
                symbol=item.symbol,
                exchange=item.exchange,
                name=name,
                sort_order=item.sort_order,
                vt_symbol=vt,
                tf_symbol=tf,
                last_price=_opt_price(q),
                change_pct=_opt_field(q, "change_pct") if q else None,
                turnover_rate=_opt_field(q, "turnover_rate"),
                volume=_opt_field(q, "volume"),
                amount=_opt_field(q, "amount"),
                volume_ratio=_opt_field(q, "volume_ratio", positive=True),
                industry=industry_by_tf.get(tf, "") if with_quotes else "",
                suspended=vt in suspended,
            )
        )
    return out


# 兼容旧测试名
_enrich = enrich
