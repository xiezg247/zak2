"""市场广度 / 排行 / 情绪梯队。"""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.models.market import EmotionLimitLadderDaily
from app.schemas.market import EmotionSnapshot, MarketOverview, RankRow
from app.services.emotion import emotion_cycle as emotion_cycle_svc
from app.services.market.db_ranks import db_rank_fallback
from app.services.market.quotes import QuoteStore, get_quote_store
from app.services.quote_collect.session import is_ashare_trading_session
from app.services.symbols import to_vt_symbol

RANK_FIELDS = (
    "change_pct",
    "turnover_rate",
    "amount",
    "volume",
    "volume_ratio",
    "limit_times",
    "intraday_change_pct",
)


def load_emotion(db: Session) -> EmotionSnapshot | None:
    row = db.scalar(select(EmotionLimitLadderDaily).order_by(EmotionLimitLadderDaily.trade_date.desc()).limit(1))
    if not row:
        return None
    linked: list[str] = []
    try:
        parsed = json.loads(row.linked_board_vt_symbols or "[]")
        if isinstance(parsed, list):
            linked = [str(x) for x in parsed]
    except json.JSONDecodeError:
        linked = []
    return EmotionSnapshot(
        trade_date=row.trade_date,
        max_limit_times=row.max_limit_times,
        max_board_vt_symbol=row.max_board_vt_symbol,
        linked_board_count=len(linked),
        linked_board_vt_symbols=linked[:30],
        updated_at=row.updated_at,
    )


def is_trading_now(db: Session) -> bool:
    """当前是否处于 A 股交易时段。

    优先查交易日历（含节假日）；日历缺今天记录时回退为「工作日 + 交易时段」判断。
    """
    today = china_today()
    cal = db.scalar(
        text("SELECT is_open FROM app.trade_calendar WHERE cal_date = :d"),
        {"d": today.isoformat()},
    )
    if cal is not None and int(cal) != 1:
        return False
    return is_ashare_trading_session()


def market_overview(db: Session) -> MarketOverview:
    store = get_quote_store()
    meta = store.meta()
    available_ranks: list[str] = []
    if meta.get("available"):
        for field in RANK_FIELDS:
            if store.list_rank(field, top_n=1):
                available_ranks.append(field)
    return MarketOverview(
        redis_available=bool(meta.get("available")),
        quote_count=int(meta.get("quote_count") or 0),
        updated_at=meta.get("updated_at"),
        is_trading=is_trading_now(db),
        emotion=load_emotion(db),
        emotion_cycle=emotion_cycle_svc.build_emotion_cycle(db),
        ranks_available=available_ranks,
    )


def _parse_tf(tf_symbol: str) -> tuple[str, str]:
    if "." not in tf_symbol:
        return tf_symbol, "SSE"
    left, right = tf_symbol.split(".", 1)
    # SHSE.600519
    from app.services.symbols import normalize_exchange

    return right, normalize_exchange(left)


def _redis_rank_rows(store: QuoteStore, field: str, ranked: list[tuple[str, float]]) -> list[RankRow]:
    quotes = {q.symbol: q for q in store.get_quotes([s for s, _ in ranked])}
    out: list[RankRow] = []
    for index, (tf, score) in enumerate(ranked, start=1):
        symbol, exchange = _parse_tf(tf)
        q = quotes.get(tf)
        out.append(
            RankRow(
                rank=index,
                symbol=symbol,
                exchange=exchange,
                vt_symbol=to_vt_symbol(symbol, exchange),
                tf_symbol=tf,
                name=q.name if q else "",
                score=float(score),
                last_price=q.last_price if q else None,
                change_pct=q.change_pct if q else (score if field == "change_pct" else None),
                change_amount=q.change_amount if q else None,
                prev_close=q.prev_close if q else None,
                open_price=q.open_price if q else None,
                high_price=q.high_price if q else None,
                low_price=q.low_price if q else None,
                turnover_rate=q.turnover_rate if q else (score if field == "turnover_rate" else None),
                amount=q.amount if q else (score if field == "amount" else None),
                volume=q.volume if q else None,
                amplitude=q.amplitude if q else None,
                volume_ratio=q.volume_ratio if q else (score if field == "volume_ratio" else None),
                net_mf_amount=q.net_mf_amount if q else None,
                limit_times=q.limit_times if q else (score if field == "limit_times" else None),
                trade_time=q.trade_time if q else None,
                industry=q.industry if q else None,
                total_mv=q.total_mv if q else None,
                circ_mv=q.circ_mv if q else None,
            )
        )
    return out


def market_ranks(db: Session, field: str, *, top_n: int = 50) -> list[RankRow]:
    if field not in RANK_FIELDS:
        raise HTTPException(status_code=400, detail=f"不支持的排行字段：{field}")

    store = get_quote_store()
    trading = is_trading_now(db)

    # 开市时优先实时 Redis 行情
    if trading and store.available():
        ranked = store.list_rank(field, top_n=top_n)
        if ranked:
            return _redis_rank_rows(store, field, ranked)

    # 休市 / Redis 空 → 回退数据库收盘数据
    rows = db_rank_fallback(db, field, top_n=top_n)
    if rows:
        return rows

    if trading and not store.available():
        raise HTTPException(status_code=503, detail="Redis 不可用，且数据库无收盘数据")
    return []
