from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.backtest import BacktestRun
from app.schemas.backtest import BacktestRunOut, BacktestRunRequest
from app.services.backtest_engine import load_daily_bars, run_double_ma
from app.services.watchlist_repo import resolve_symbol_pair
from app.services.symbols import to_vt_symbol


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat(sep=" ")


def _to_out(row: BacktestRun, *, detail: bool = False) -> BacktestRunOut:
    stats: dict[str, Any] = {}
    equity: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    try:
        raw = json.loads(row.raw_statistics_json or "{}")
        if isinstance(raw, dict):
            stats = dict(raw.get("statistics") or {k: v for k, v in raw.items() if k not in {"equity_curve", "trades"}})
            if detail:
                equity = list(raw.get("equity_curve") or [])
                trades = list(raw.get("trades") or [])
    except json.JSONDecodeError:
        stats = {}
    return BacktestRunOut(
        id=row.id,
        vt_symbol=row.vt_symbol,
        strategy=row.strategy,
        interval=row.interval,
        start_date=row.start_date,
        end_date=row.end_date,
        total_return=row.total_return,
        max_drawdown=row.max_drawdown,
        sharpe_ratio=row.sharpe_ratio,
        trade_count=row.trade_count,
        source=row.source,
        batch_id=row.batch_id,
        statistics=stats,
        created_at=row.created_at,
        equity_curve=equity,
        trades=trades,
    )


def list_runs(db: Session, user_id: str, *, limit: int = 50, batch_id: str | None = None) -> list[BacktestRunOut]:
    stmt = select(BacktestRun).where(BacktestRun.user_id == user_id)
    if batch_id:
        stmt = stmt.where(BacktestRun.batch_id == batch_id)
    rows = db.scalars(stmt.order_by(desc(BacktestRun.created_at)).limit(limit))
    return [_to_out(r) for r in rows]


def get_run(db: Session, user_id: str, run_id: str) -> BacktestRunOut | None:
    row = db.scalar(select(BacktestRun).where(BacktestRun.id == run_id, BacktestRun.user_id == user_id))
    if not row:
        return None
    return _to_out(row, detail=True)


def list_batches(db: Session, user_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(BacktestRun)
            .where(BacktestRun.user_id == user_id, BacktestRun.batch_id.is_not(None))
            .order_by(desc(BacktestRun.created_at))
            .limit(500)
        )
    )
    batches: dict[str, dict[str, Any]] = {}
    for r in rows:
        bid = r.batch_id or ""
        if not bid:
            continue
        item = batches.get(bid)
        if not item:
            item = {
                "batch_id": bid,
                "strategy": r.strategy,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "created_at": r.created_at,
                "count": 0,
            }
            batches[bid] = item
        item["count"] += 1
    out = sorted(batches.values(), key=lambda x: x["created_at"], reverse=True)
    return out[:limit]


def save_run(
    db: Session,
    *,
    user_id: str,
    vt_symbol: str,
    strategy: str,
    interval: str,
    start_date: str,
    end_date: str,
    result: dict[str, Any],
    source: str = "single",
    batch_id: str | None = None,
) -> BacktestRun:
    symbol, exchange = resolve_symbol_pair(vt_symbol)
    vt = to_vt_symbol(symbol, exchange)
    row = BacktestRun(
        id=uuid4().hex,
        user_id=user_id,
        vt_symbol=vt,
        strategy=strategy,
        interval=interval,
        start_date=start_date[:10],
        end_date=end_date[:10],
        total_return=result.get("total_return"),
        max_drawdown=result.get("max_drawdown"),
        sharpe_ratio=result.get("sharpe_ratio"),
        trade_count=result.get("trade_count"),
        source=source,
        batch_id=batch_id,
        raw_statistics_json=json.dumps(result, ensure_ascii=False),
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def execute_single(db: Session, user_id: str, req: BacktestRunRequest, *, batch_id: str | None = None, source: str = "single") -> BacktestRunOut:
    if req.strategy != "double_ma":
        raise HTTPException(status_code=501, detail=f"策略「{req.strategy}」尚未实现（P5 仅 double_ma）")
    bars = load_daily_bars(db, vt_symbol=req.vt_symbol, start_date=req.start_date, end_date=req.end_date)
    result = run_double_ma(
        bars,
        fast_window=req.fast_window,
        slow_window=req.slow_window,
        capital=req.capital,
    )
    row = save_run(
        db,
        user_id=user_id,
        vt_symbol=req.vt_symbol,
        strategy="double_ma",
        interval=req.interval or "d",
        start_date=req.start_date,
        end_date=req.end_date,
        result=result,
        source=source,
        batch_id=batch_id,
    )
    return _to_out(row, detail=True)
