"""行情 Provider：Protocol + TickFlow。"""

from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Protocol

from app.integrations.tickflow.client import get_tickflow_client
from app.services.quote_collect.models import QuoteSnapshot
from app.services.symbols import from_tickflow_symbol, to_tickflow_symbol

QUOTE_BATCH_SIZE = 80
DEFAULT_QUOTE_FETCH_MAX_WORKERS = 1
_RATE_LIMIT_MAX_ATTEMPTS = 3
_RATE_LIMIT_RE = re.compile(r"请\s*(\d+(?:\.\d+)?)\s*ms")


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
        volume_ratio=_f(row, "ext.volume_ratio", "volume_ratio"),
        net_mf_amount=_f(row, "ext.net_mf_amount", "net_mf_amount"),
        limit_times=_f(row, "ext.limit_times", "limit_times"),
        trade_time=str(row.get("trade_time", "") or row.get("ext.trade_time", "") or ""),
        industry=str(row.get("ext.industry", "") or row.get("industry", "") or ""),
        total_mv=_f(row, "ext.total_mv", "total_mv"),
        circ_mv=_f(row, "ext.circ_mv", "circ_mv"),
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


def _rate_limit_wait(exc: BaseException) -> float | None:
    """解析 TickFlow 429 提示中的服务端建议等待时长（如「请 44ms 后重试」）。

    返回秒数并留 1.5 倍余量；无法解析时返回 None（交由调用方按退避处理）。
    """
    if type(exc).__name__ != "RateLimitError":
        return None
    m = _RATE_LIMIT_RE.search(str(exc))
    if not m:
        return None
    return min(5.0, float(m.group(1)) / 1000.0 * 1.5 + 0.1)


class TickFlowProvider:
    name = "tickflow"

    def __init__(
        self,
        *,
        api_key: str = "",
        max_retries: int | None = None,
        timeout: float | None = None,
        batch_delay_ms: int = 0,
    ) -> None:
        self._api_key = api_key
        self._max_retries = max_retries
        self._timeout = timeout
        self._batch_delay_s = max(0, int(batch_delay_ms)) / 1000.0

    def fetch(self, symbols: list[str]) -> dict[str, QuoteSnapshot]:
        if not symbols:
            return {}
        batches = [symbols[start : start + QUOTE_BATCH_SIZE] for start in range(0, len(symbols), QUOTE_BATCH_SIZE)]
        workers = quote_fetch_max_workers(batch_count=len(batches))
        result: dict[str, QuoteSnapshot] = {}

        def _one(batch: list[str]) -> dict[str, QuoteSnapshot]:
            if self._batch_delay_s > 0:
                time.sleep(self._batch_delay_s)
            client = get_tickflow_client(
                api_key=self._api_key,
                max_retries=self._max_retries,
                timeout=self._timeout,
            )
            last_error: BaseException | None = None
            for attempt in range(_RATE_LIMIT_MAX_ATTEMPTS):
                try:
                    # 官方 SDK 使用「代码.SH/SZ/BJ」格式，与内部 tf_symbol 互换
                    tc_batch = [to_tickflow_symbol(s) for s in batch]
                    df = client.quotes.get(symbols=tc_batch, as_dataframe=True)
                    quotes = _quotes_from_dataframe(df)
                    remapped: dict[str, QuoteSnapshot] = {}
                    for tc_symbol, quote in quotes.items():
                        tf_symbol = from_tickflow_symbol(tc_symbol)
                        quote.symbol = tf_symbol
                        remapped[tf_symbol] = quote
                    return remapped
                except BaseException as exc:  # noqa: BLE001 — SDK 异常兜底后按限流补偿
                    last_error = exc
                    wait = _rate_limit_wait(exc)
                    if wait is None or attempt + 1 >= _RATE_LIMIT_MAX_ATTEMPTS:
                        raise
                    time.sleep(wait)
            assert last_error is not None
            raise last_error

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
