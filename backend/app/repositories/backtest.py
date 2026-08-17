from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import desc, select

from app.models.backtest import BacktestRun
from app.repositories.base import BaseRepository
from app.repositories.pagination import Page, paginate
from app.repositories.watchlist import resolve_symbol_pair
from app.schemas.backtest import BacktestRunOut, BacktestRunRequest, OptimizeSummaryOut
from app.services.backtest_bars import bars_to_records, load_bars
from app.services.backtest_optimize import pick_best
from app.services.backtest_settings import build_strategy_setting, min_bars_for_request
from app.services.symbols import to_vt_symbol


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat(sep=" ")


def _params_dict(row: BacktestRun) -> dict[str, Any]:
    try:
        raw = json.loads(row.params_json or "{}")
        return raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        return {}


class BacktestRepository(BaseRepository[BacktestRun]):
    """回测运行记录仓库。"""

    model = BacktestRun
    order_by = (desc(BacktestRun.created_at),)

    # ---- 查询 ----

    def list_runs(self, *, limit: int = 50, batch_id: str | None = None) -> list[BacktestRunOut]:
        stmt = select(BacktestRun).where(BacktestRun.user_id == self.user_id)
        if batch_id:
            stmt = stmt.where(BacktestRun.batch_id == batch_id)
        rows = self.db.scalars(stmt.order_by(desc(BacktestRun.created_at)).limit(limit))
        return [self.to_out(r) for r in rows]

    def list_runs_page(
        self, *, page: int = 1, page_size: int = 20, batch_id: str | None = None
    ) -> Page[BacktestRunOut]:
        stmt = select(BacktestRun).where(BacktestRun.user_id == self.user_id)
        if batch_id:
            stmt = stmt.where(BacktestRun.batch_id == batch_id)
        return paginate(self.db, stmt.order_by(desc(BacktestRun.created_at)), page=page, page_size=page_size).map(
            self.to_out
        )

    def get_run(self, run_id: str) -> BacktestRunOut | None:
        row = self.get(run_id)
        if not row:
            return None
        return self.to_out(row, detail=True)

    def list_batches(self, *, limit: int = 30) -> list[dict[str, Any]]:
        rows = list(
            self.db.scalars(
                select(BacktestRun)
                .where(BacktestRun.user_id == self.user_id, BacktestRun.batch_id.is_not(None))
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

    # ---- 写 ----

    def save_run(
        self,
        *,
        vt_symbol: str,
        strategy: str,
        interval: str,
        start_date: str,
        end_date: str,
        result: dict[str, Any],
        source: str = "single",
        batch_id: str | None = None,
        engine: str | None = "vnpy",
        params: dict[str, Any] | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> BacktestRun:
        symbol, exchange = resolve_symbol_pair(vt_symbol)
        vt = to_vt_symbol(symbol, exchange)
        return self.create(
            id=uuid4().hex,
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
            engine=engine,
            params_json=json.dumps(params or {}, ensure_ascii=False),
            status=status,
            error_message=error_message,
            created_at=_now(),
        )

    # ---- 转换与引擎（供 worker 复用） ----

    def to_out(self, row: BacktestRun, *, detail: bool = False) -> BacktestRunOut:
        stats: dict[str, Any] = {}
        equity: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        try:
            raw = json.loads(row.raw_statistics_json or "{}")
            if isinstance(raw, dict):
                stats = dict(
                    raw.get("statistics") or {k: v for k, v in raw.items() if k not in {"equity_curve", "trades"}}
                )
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
            engine=row.engine,
            status=row.status or "success",
            error_message=row.error_message,
            params=_params_dict(row),
        )

    def load_bars_for_request(self, req: BacktestRunRequest):
        interval = req.interval or "d"
        return load_bars(
            self.db,
            vt_symbol=req.vt_symbol,
            start_date=req.start_date,
            end_date=req.end_date,
            interval=interval,
            min_bars=min_bars_for_request(req),
            max_trading_days=req.max_trading_days if interval == "1m" else None,
        )

    def run_vnpy(self, req: BacktestRunRequest, bars) -> dict[str, Any]:
        try:
            from app.services.backtest_vnpy import run_cta_backtest
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="vnpy 未安装：请使用 backtest-worker（pip/uv extra backtest）",
            ) from exc

        setting = build_strategy_setting(req)
        return run_cta_backtest(
            bars_to_records(bars),
            vt_symbol=req.vt_symbol,
            strategy_id=req.strategy,
            setting=setting,
            start=req.start_date,
            end=req.end_date,
            capital=req.capital,
            rate=req.rate,
            slippage=req.slippage,
            stamp_duty=req.stamp_duty,
            interval=req.interval or "d",
        )

    # ---- 执行 ----

    def execute_single(
        self,
        req: BacktestRunRequest,
        *,
        batch_id: str | None = None,
        source: str = "single",
    ) -> BacktestRunOut:
        if req.fast_window >= req.slow_window:
            raise HTTPException(status_code=400, detail="fast_window 须小于 slow_window")
        try:
            from app.strategies.cta.registry import get_strategy_class

            get_strategy_class(req.strategy)
        except KeyError as exc:
            raise HTTPException(status_code=501, detail=f"策略「{req.strategy}」尚未实现") from exc

        setting = build_strategy_setting(req)
        params = {
            "fast_window": req.fast_window,
            "slow_window": req.slow_window,
            "capital": req.capital,
            "rate": req.rate,
            "slippage": req.slippage,
            "stamp_duty": req.stamp_duty,
            "adx_period": req.adx_period,
            "adx_threshold": req.adx_threshold,
            "trailing_stop_pct": req.trailing_stop_pct,
            "interval": req.interval or "d",
            "max_trading_days": req.max_trading_days,
            "setting": setting,
        }

        try:
            bars = self.load_bars_for_request(req)
            result = self.run_vnpy(req, bars)
            row = self.save_run(
                vt_symbol=req.vt_symbol,
                strategy=req.strategy,
                interval=req.interval or "d",
                start_date=req.start_date,
                end_date=req.end_date,
                result=result,
                source=source,
                batch_id=batch_id,
                engine="vnpy",
                params=params,
                status="success",
            )
        except HTTPException as exc:
            row = self.save_run(
                vt_symbol=req.vt_symbol,
                strategy=req.strategy,
                interval=req.interval or "d",
                start_date=req.start_date,
                end_date=req.end_date,
                result={},
                source=source,
                batch_id=batch_id,
                engine="vnpy",
                params=params,
                status="failed",
                error_message=str(exc.detail),
            )
            if source == "single":
                raise
            return self.to_out(row, detail=True)
        except Exception as exc:  # noqa: BLE001
            row = self.save_run(
                vt_symbol=req.vt_symbol,
                strategy=req.strategy,
                interval=req.interval or "d",
                start_date=req.start_date,
                end_date=req.end_date,
                result={},
                source=source,
                batch_id=batch_id,
                engine="vnpy",
                params=params,
                status="failed",
                error_message=str(exc),
            )
            if source == "single":
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            return self.to_out(row, detail=True)

        return self.to_out(row, detail=True)

    def summarize_optimize(
        self,
        batch_id: str,
        *,
        objective: str = "sharpe_ratio",
    ) -> OptimizeSummaryOut:
        runs = self.list_runs(limit=200, batch_id=batch_id)
        success = [r for r in runs if r.status == "success"]
        as_dicts = [
            {
                "id": r.id,
                "sharpe_ratio": r.sharpe_ratio,
                "total_return": r.total_return,
                "max_drawdown": r.max_drawdown,
                "_run": r,
            }
            for r in success
        ]
        best_row = pick_best(as_dicts, objective=objective)
        best = best_row["_run"] if best_row else None
        return OptimizeSummaryOut(batch_id=batch_id, objective=objective, best=best, runs=runs)
