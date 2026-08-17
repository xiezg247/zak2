"""行情 Provider：Protocol + TickFlow。"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Protocol

from app.integrations.tickflow.client import get_tickflow_client
from app.services.quote_collect.models import QuoteSnapshot

QUOTE_BATCH_SIZE = 80
DEFAULT_QUOTE_FETCH_MAX_WORKERS = 4


class QuoteProvider(Protocol):
    name: str

    def fetch(self, symbols: list[str]) -> dict[str, QuoteSnapshot]: ...


def _f(row: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in row and row[key] is not None and row[key] != "":
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return default


def parse_tickflow_row(row: dict[str, Any]) -> QuoteSnapshot:
    name = str(row.get("ext.name", "") or row.get("name", "") or "")
    change_pct = _f(row, "ext.change_pct", "change_pct") * 100
    change_amount = _f(row, "ext.change_amount", "change_amount")
    turnover_rate = _f(row, "ext.turnover_rate", "turnover_rate") * 100
    amplitude = _f(row, "ext.amplitude", "amplitude") * 100
    symbol = str(row.get("symbol", "") or "")
    return QuoteSnapshot(
        symbol=symbol,
        name=name,
        last_price=_f(row, "last_price"),
        prev_close=_f(row, "prev_close"),
        open_price=_f(row, "open", "open_price"),
        high_price=_f(row, "high", "high_price"),
        low_price=_f(row, "low", "low_price"),
        change_amount=change_amount,
        change_pct=change_pct,
        turnover_rate=turnover_rate,
        volume=_f(row, "volume"),
        amount=_f(row, "amount"),
        amplitude=amplitude,
    )


def _quotes_from_dataframe(df: Any) -> dict[str, QuoteSnapshot]:
    if df is None:
        return {}
    empty = getattr(df, "empty", None)
    if empty is True:
        return {}
    result: dict[str, QuoteSnapshot] = {}
    if hasattr(df, "iterrows"):
        for idx, row in df.iterrows():
            data = row.to_dict() if hasattr(row, "to_dict") else dict(row)
            if not data.get("symbol"):
                data["symbol"] = str(idx)
            quote = parse_tickflow_row(data)
            if quote.symbol:
                result[quote.symbol] = quote
        return result
    if isinstance(df, list):
        for item in df:
            if isinstance(item, dict):
                quote = parse_tickflow_row(item)
                if quote.symbol:
                    result[quote.symbol] = quote
    return result


def quote_fetch_max_workers(*, batch_count: int) -> int:
    raw = os.getenv("QUOTE_FETCH_MAX_WORKERS", str(DEFAULT_QUOTE_FETCH_MAX_WORKERS)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = DEFAULT_QUOTE_FETCH_MAX_WORKERS
    configured = max(1, min(configured, 8))
    return min(configured, max(1, batch_count))


class TickFlowProvider:
    name = "tickflow"

    def __init__(self, *, api_key: str = "") -> None:
        self._api_key = api_key

    def fetch(self, symbols: list[str]) -> dict[str, QuoteSnapshot]:
        if not symbols:
            return {}
        batches = [symbols[start : start + QUOTE_BATCH_SIZE] for start in range(0, len(symbols), QUOTE_BATCH_SIZE)]
        workers = quote_fetch_max_workers(batch_count=len(batches))
        result: dict[str, QuoteSnapshot] = {}

        def _one(batch: list[str]) -> dict[str, QuoteSnapshot]:
            client = get_tickflow_client(api_key=self._api_key)
            df = client.quotes.get(symbols=batch, as_dataframe=True)
            return _quotes_from_dataframe(df)

        if workers <= 1 or len(batches) <= 1:
            for batch in batches:
                result.update(_one(batch))
            return result

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_one, batch) for batch in batches]
            for fut in as_completed(futures):
                result.update(fut.result())
        return result


def get_provider(name: str | None = None) -> QuoteProvider:
    key = (name or "tickflow").strip().lower() or "tickflow"
    if key == "tickflow":
        return TickFlowProvider()
    raise ValueError(f"未知行情 Provider：{name}")
