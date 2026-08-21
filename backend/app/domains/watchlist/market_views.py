"""行情视图：quotes / fundamentals / bars。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import Unavailable
from app.domains.watchlist.enrich import _opt_field, _opt_price
from app.domains.watchlist.repository import resolve_symbol_pair
from app.domains.watchlist.schemas import BarsResponse, FundamentalsOut, QuoteOut
from app.domains.market import fundamentals as fundamentals_svc
from app.domains.market.bars import load_bars
from app.domains.market.quotes import QuoteRow, get_quote_store
from app.domains.market.stock_industry import enrich_rows_from_db
from app.services.symbols import normalize_exchange, to_tf_symbol, to_vt_symbol


def get_quotes(db: Session, symbols: str) -> list[QuoteOut]:
    store = get_quote_store()
    if not store.available():
        raise Unavailable("Redis 不可用")
    tf_list: list[str] = []
    meta: list[tuple[str, str, str]] = []
    for raw in symbols.split(","):
        raw = raw.strip()
        if not raw:
            continue
        symbol, exchange = resolve_symbol_pair(raw)
        tf = to_tf_symbol(symbol, exchange)
        tf_list.append(tf)
        meta.append((symbol, normalize_exchange(exchange), tf))
    quotes = {q.symbol: q for q in store.get_quotes(tf_list)}
    rows: list[QuoteRow] = []
    for _, _, tf in meta:
        q = quotes.get(tf)
        rows.append(
            QuoteRow(
                symbol=tf,
                name=q.name if q else "",
                last_price=q.last_price if q else 0.0,
                change_pct=q.change_pct if q else 0.0,
                turnover_rate=q.turnover_rate if q else 0.0,
                volume=q.volume if q else 0.0,
                amount=q.amount if q else 0.0,
                amplitude=q.amplitude if q else 0.0,
                volume_ratio=q.volume_ratio if q else 0.0,
                industry=(q.industry if q else "") or "",
            )
        )
    enrich_rows_from_db(db, rows)
    out: list[QuoteOut] = []
    for (symbol, exchange, tf), row in zip(meta, rows, strict=True):
        q = quotes.get(tf)
        out.append(
            QuoteOut(
                symbol=symbol,
                exchange=exchange,
                vt_symbol=to_vt_symbol(symbol, exchange),
                tf_symbol=tf,
                name=row.name,
                last_price=_opt_price(q),
                change_pct=_opt_field(q, "change_pct") if q else None,
                turnover_rate=_opt_field(q, "turnover_rate"),
                volume=_opt_field(q, "volume"),
                amount=_opt_field(q, "amount"),
                amplitude=_opt_field(q, "amplitude"),
                volume_ratio=_opt_field(q, "volume_ratio", positive=True),
                industry=row.industry or "",
            )
        )
    return out


def get_fundamentals(db: Session, vt_symbol: str) -> FundamentalsOut:
    return fundamentals_svc.get_fundamentals(db, vt_symbol)


def get_bars(
    db: Session,
    vt_symbol: str,
    *,
    interval: str = "d",
    limit: int = 120,
) -> BarsResponse:
    symbol, exchange = resolve_symbol_pair(vt_symbol)
    return load_bars(db, symbol=symbol, exchange=exchange, interval=interval, limit=limit)
