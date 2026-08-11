"""Redis 行情写入（键兼容现网 QuoteStore）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.quote_collect.models import QuoteSnapshot

KEY_PREFIX = "zak"
QUOTE_KEY_FMT = f"{KEY_PREFIX}:quote:{{symbol}}"
RANK_KEY_FMT = f"{KEY_PREFIX}:rank:{{field}}"
META_UPDATED_AT_KEY = f"{KEY_PREFIX}:meta:updated_at"
META_QUOTE_COUNT_KEY = f"{KEY_PREFIX}:meta:quote_count"
META_SEQ_KEY = f"{KEY_PREFIX}:meta:seq"
NOTIFY_CHANNEL = f"{KEY_PREFIX}:notify:quotes"

FULL_RANK_FIELDS: tuple[str, ...] = (
    "change_pct",
    "turnover_rate",
    "amount",
    "volume",
    "amplitude",
)
SPARSE_RANK_FIELDS: tuple[str, ...] = (
    "volume_ratio",
    "net_mf_amount",
    "limit_times",
)


def snapshot_to_hash(quote: QuoteSnapshot) -> dict[str, str]:
    return {
        "symbol": quote.symbol,
        "name": quote.name or "",
        "last_price": str(quote.last_price),
        "prev_close": str(quote.prev_close),
        "open_price": str(quote.open_price),
        "high_price": str(quote.high_price),
        "low_price": str(quote.low_price),
        "change_amount": str(quote.change_amount),
        "change_pct": str(quote.change_pct),
        "turnover_rate": str(quote.turnover_rate),
        "volume": str(quote.volume),
        "amount": str(quote.amount),
        "amplitude": str(quote.amplitude),
        "volume_ratio": str(quote.volume_ratio),
        "net_mf_amount": str(quote.net_mf_amount),
        "limit_times": str(quote.limit_times),
        "trade_time": quote.trade_time or "",
        "industry": quote.industry or "",
        "total_mv": str(quote.total_mv),
        "circ_mv": str(quote.circ_mv),
    }


class RedisQuoteWriter:
    def __init__(self, client: Any) -> None:
        self._client = client

    def write_quotes(self, quotes: dict[str, QuoteSnapshot]) -> int:
        if not quotes:
            return 0

        pipe = self._client.pipeline(transaction=False)
        pipe.incr(META_SEQ_KEY)

        rank_members: dict[str, list[tuple[float, str]]] = {
            field: [] for field in (*FULL_RANK_FIELDS, *SPARSE_RANK_FIELDS)
        }

        for tf_symbol, quote in quotes.items():
            key = QUOTE_KEY_FMT.format(symbol=tf_symbol)
            pipe.hset(key, mapping=snapshot_to_hash(quote))
            rank_members["change_pct"].append((quote.change_pct, tf_symbol))
            rank_members["turnover_rate"].append((quote.turnover_rate, tf_symbol))
            rank_members["amount"].append((quote.amount, tf_symbol))
            rank_members["volume"].append((quote.volume, tf_symbol))
            rank_members["amplitude"].append((quote.amplitude, tf_symbol))
            if quote.volume_ratio > 0:
                rank_members["volume_ratio"].append((quote.volume_ratio, tf_symbol))
            if quote.net_mf_amount != 0:
                rank_members["net_mf_amount"].append((quote.net_mf_amount, tf_symbol))
            if quote.limit_times >= 1:
                rank_members["limit_times"].append((quote.limit_times, tf_symbol))

        for field in (*FULL_RANK_FIELDS, *SPARSE_RANK_FIELDS):
            rank_key = RANK_KEY_FMT.format(field=field)
            pipe.delete(rank_key)
            members = rank_members[field]
            if members:
                mapping = {sym: score for score, sym in members}
                pipe.zadd(rank_key, mapping)

        pipe.set(META_UPDATED_AT_KEY, datetime.now().isoformat(timespec="seconds"))
        pipe.set(META_QUOTE_COUNT_KEY, str(len(quotes)))
        results = pipe.execute()
        new_seq = int(results[0]) if results else 0
        if new_seq > 0:
            self._client.publish(NOTIFY_CHANNEL, str(new_seq))
        return len(quotes)
