"""Redis 行情读取（兼容 zak 键名与短 field）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import redis

from app.core.settings import get_settings

KEY_PREFIX = "zak"
RANK_KEY_FMT = f"{KEY_PREFIX}:rank:{{field}}"
QUOTE_KEY_FMT = f"{KEY_PREFIX}:quote:{{symbol}}"
QUOTE_BLOB_KEY_FMT = f"{KEY_PREFIX}:quote:b:{{symbol}}"
META_UPDATED_AT_KEY = f"{KEY_PREFIX}:meta:updated_at"
META_QUOTE_COUNT_KEY = f"{KEY_PREFIX}:meta:quote_count"

SHORT_TO_LONG = {
    "s": "symbol",
    "n": "name",
    "lp": "last_price",
    "pc": "prev_close",
    "op": "open_price",
    "hi": "high_price",
    "lo": "low_price",
    "ca": "change_amount",
    "cp": "change_pct",
    "tr": "turnover_rate",
    "v": "volume",
    "a": "amount",
    "amp": "amplitude",
    "vr": "volume_ratio",
    "nmf": "net_mf_amount",
    "cs5": "change_speed_5m",
    "lt": "limit_times",
    "tt": "trade_time",
    "tm": "total_mv",
    "cm": "circ_mv",
    "ind": "industry",
}


@dataclass
class QuoteRow:
    symbol: str
    name: str = ""
    last_price: float = 0.0
    change_pct: float = 0.0
    turnover_rate: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    amplitude: float = 0.0
    volume_ratio: float = 0.0
    net_mf_amount: float = 0.0
    limit_times: float = 0.0
    industry: str = ""
    total_mv: float = 0.0  # 万元（与 Tushare daily_basic 一致）
    circ_mv: float = 0.0

    def to_result_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "vt_symbol": _to_vt_symbol(self.symbol),
            "name": self.name,
            "last_price": self.last_price,
            "change_pct": self.change_pct,
            "turnover_rate": self.turnover_rate,
            "volume": self.volume,
            "amount": self.amount,
            "amplitude": self.amplitude,
            "volume_ratio": self.volume_ratio,
            "net_mf_amount": self.net_mf_amount,
            "limit_times": self.limit_times,
            "industry": self.industry,
            "total_mv": self.total_mv,
            "circ_mv": self.circ_mv,
        }


def _to_vt_symbol(tf_symbol: str) -> str:
    """SHSE.600519 → 600519.SSE；SZSE.000001 → 000001.SZSE。"""
    if "." not in tf_symbol:
        return tf_symbol
    exchange, code = tf_symbol.split(".", 1)
    mapping = {"SHSE": "SSE", "SZSE": "SZSE", "BJSE": "BSE"}
    return f"{code}.{mapping.get(exchange, exchange)}"


def normalize_hash(data: dict[str, str]) -> dict[str, str]:
    if not data:
        return data
    if not any(key in SHORT_TO_LONG for key in data):
        return data
    out: dict[str, str] = {}
    for key, value in data.items():
        out[SHORT_TO_LONG.get(key, key)] = value
    return out


def _f(data: dict[str, str], key: str, default: float = 0.0) -> float:
    raw = data.get(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def hash_to_quote(symbol: str, data: dict[str, str]) -> QuoteRow:
    norm = normalize_hash(data)
    return QuoteRow(
        symbol=norm.get("symbol") or symbol,
        name=norm.get("name") or "",
        last_price=_f(norm, "last_price"),
        change_pct=_f(norm, "change_pct"),
        turnover_rate=_f(norm, "turnover_rate"),
        volume=_f(norm, "volume"),
        amount=_f(norm, "amount"),
        amplitude=_f(norm, "amplitude"),
        volume_ratio=_f(norm, "volume_ratio"),
        net_mf_amount=_f(norm, "net_mf_amount"),
        limit_times=_f(norm, "limit_times"),
        industry=str(norm.get("industry") or "").strip(),
        total_mv=_f(norm, "total_mv"),
        circ_mv=_f(norm, "circ_mv"),
    )


class QuoteStore:
    def __init__(self, url: str | None = None) -> None:
        settings = get_settings()
        self._url = url or settings.redis_url
        self._client: redis.Redis | None = None

    def _conn(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self._url, decode_responses=True)
        return self._client

    def available(self) -> bool:
        try:
            return bool(self._conn().ping())
        except redis.RedisError:
            return False

    def meta(self) -> dict[str, Any]:
        try:
            client = self._conn()
            return {
                "updated_at": client.get(META_UPDATED_AT_KEY),
                "quote_count": int(client.get(META_QUOTE_COUNT_KEY) or 0),
                "available": True,
            }
        except redis.RedisError:
            return {"updated_at": None, "quote_count": 0, "available": False}

    def list_rank(self, field: str, *, top_n: int = 200) -> list[tuple[str, float]]:
        client = self._conn()
        key = RANK_KEY_FMT.format(field=field)
        raw = client.zrevrange(key, 0, max(0, top_n - 1), withscores=True)
        return [(str(member), float(score)) for member, score in raw]

    def get_quotes(self, symbols: list[str]) -> list[QuoteRow]:
        if not symbols:
            return []
        client = self._conn()
        pipe = client.pipeline(transaction=False)
        for symbol in symbols:
            pipe.hgetall(QUOTE_KEY_FMT.format(symbol=symbol))
        hashes = pipe.execute()
        rows: list[QuoteRow] = []
        missing: list[str] = []
        for symbol, data in zip(symbols, hashes, strict=True):
            if data:
                rows.append(hash_to_quote(symbol, data))
            else:
                missing.append(symbol)
        if missing:
            pipe2 = client.pipeline(transaction=False)
            for symbol in missing:
                pipe2.get(QUOTE_BLOB_KEY_FMT.format(symbol=symbol))
            blobs = pipe2.execute()
            for symbol, blob in zip(missing, blobs, strict=True):
                if not blob:
                    continue
                try:
                    loaded = json.loads(blob)
                except json.JSONDecodeError:
                    continue
                if isinstance(loaded, dict):
                    rows.append(hash_to_quote(symbol, {str(k): str(v) for k, v in loaded.items()}))
        return rows

    def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
        ranked = self.list_rank(field, top_n=pool)
        if not ranked:
            return []
        score_map = {symbol: score for symbol, score in ranked}
        quotes = self.get_quotes([symbol for symbol, _ in ranked])
        # 若 hash 缺字段，用 zset score 回填主排序字段
        field_attr = {
            "change_pct": "change_pct",
            "turnover_rate": "turnover_rate",
            "amount": "amount",
            "volume": "volume",
            "volume_ratio": "volume_ratio",
            "net_mf_amount": "net_mf_amount",
            "limit_times": "limit_times",
            "total_mv": "total_mv",
        }.get(field)
        for quote in quotes:
            if field_attr and getattr(quote, field_attr) == 0.0 and quote.symbol in score_map:
                setattr(quote, field_attr, score_map[quote.symbol])
        order = {symbol: i for i, (symbol, _) in enumerate(ranked)}
        quotes.sort(key=lambda q: order.get(q.symbol, 10**9))
        return quotes


_quote_store: QuoteStore | None = None


def get_quote_store() -> QuoteStore:
    global _quote_store
    if _quote_store is None:
        _quote_store = QuoteStore()
    return _quote_store
