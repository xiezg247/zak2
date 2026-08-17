"""自选持仓记账 CRUD（投研层，非实盘）。

原生 SQL 操作 app.watchlist_positions，无对应 ORM 模型，故不继承
BaseRepository，仅保持 ``PositionRepository(db, user_id)`` 构造约定。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories.watchlist import WatchlistItemRepository
from app.services.symbols import normalize_exchange, to_vt_symbol

POSITION_MAX_ITEMS = 20
LOT_SIZE = 100
PRICE_TICK = 0.01
_CHINA_TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CHINA_TZ).replace(microsecond=0).isoformat()


def _china_today() -> str:
    return datetime.now(_CHINA_TZ).strftime("%Y-%m-%d")


def normalize_cost_price(cost_price: float) -> float:
    price = float(cost_price)
    if price <= 0:
        return price
    return round(round(price / PRICE_TICK) * PRICE_TICK, 4)


def normalize_volume(volume: int) -> int:
    v = int(volume)
    if v <= 0:
        return 0
    return (v // LOT_SIZE) * LOT_SIZE


def validate_inputs(*, cost_price: float, volume: int, buy_date: str) -> None:
    if cost_price <= 0:
        raise HTTPException(status_code=400, detail="成本价须大于 0")
    normalized = normalize_volume(volume)
    if normalized <= 0 or volume % LOT_SIZE != 0:
        raise HTTPException(status_code=400, detail="持仓量须为 100 股整数倍")
    try:
        parsed = datetime.strptime(buy_date[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="买入日格式须为 YYYY-MM-DD") from exc
    today = datetime.now(_CHINA_TZ).date()
    if parsed > today:
        raise HTTPException(status_code=400, detail="买入日不能晚于今日")


class PositionRepository:
    """持仓记账仓库（原生 SQL，返回 dict）。"""

    def __init__(self, db: Session, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    def _in_watchlist(self, symbol: str, exchange: str) -> bool:
        items = WatchlistItemRepository(self.db, self.user_id).list_items()
        exch = normalize_exchange(exchange)
        return any(i.symbol == symbol and normalize_exchange(i.exchange) == exch for i in items)

    def list_positions(self) -> list[dict]:
        rows = self.db.execute(
            text(
                """
                SELECT symbol, exchange, cost_price, volume, buy_date, notes, source, plan_pct, sort_order,
                       created_at, updated_at
                FROM app.watchlist_positions
                WHERE user_id = CAST(:uid AS uuid)
                ORDER BY sort_order, buy_date DESC
                """
            ),
            {"uid": self.user_id},
        ).mappings().all()
        out = []
        for row in rows:
            symbol = str(row["symbol"])
            exchange = normalize_exchange(str(row["exchange"]))
            out.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "vt_symbol": to_vt_symbol(symbol, exchange),
                    "cost_price": float(row["cost_price"]),
                    "volume": int(row["volume"]),
                    "buy_date": str(row["buy_date"])[:10],
                    "notes": str(row["notes"] or ""),
                    "source": str(row["source"] or "manual"),
                    "plan_pct": float(row["plan_pct"]) if row["plan_pct"] is not None else None,
                    "sort_order": int(row["sort_order"] or 0),
                    "created_at": str(row["created_at"] or ""),
                    "updated_at": str(row["updated_at"] or ""),
                }
            )
        return out

    def get_position(self, symbol: str, exchange: str) -> dict | None:
        exch = normalize_exchange(exchange)
        for row in self.list_positions():
            if row["symbol"] == symbol and row["exchange"] == exch:
                return row
        return None

    def add_position(
        self,
        *,
        symbol: str,
        exchange: str,
        cost_price: float,
        volume: int,
        buy_date: str,
        notes: str = "",
        plan_pct: float | None = None,
    ) -> dict:
        validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        exch = normalize_exchange(exchange)
        if not self._in_watchlist(symbol, exch):
            raise HTTPException(status_code=400, detail="须先加入自选再录入持仓")
        if self.get_position(symbol, exch):
            raise HTTPException(status_code=409, detail="该标的已有持仓记录")
        count = len(self.list_positions())
        if count >= POSITION_MAX_ITEMS:
            raise HTTPException(status_code=400, detail=f"持仓已满（上限 {POSITION_MAX_ITEMS}）")

        now = _now_iso()
        self.db.execute(
            text(
                """
                INSERT INTO app.watchlist_positions (
                  user_id, symbol, exchange, cost_price, volume, buy_date, notes, source,
                  plan_pct, sort_order, created_at, updated_at
                ) VALUES (
                  CAST(:uid AS uuid), :symbol, :exchange, :cost, :volume, :buy_date, :notes, 'manual',
                  :plan_pct, :sort_order, :now, :now
                )
                """
            ),
            {
                "uid": self.user_id,
                "symbol": symbol,
                "exchange": exch,
                "cost": normalize_cost_price(cost_price),
                "volume": normalize_volume(volume),
                "buy_date": buy_date[:10],
                "notes": (notes or "").strip(),
                "plan_pct": plan_pct,
                "sort_order": count,
                "now": now,
            },
        )
        self.db.commit()
        row = self.get_position(symbol, exch)
        assert row is not None
        return row

    def update_position(
        self,
        *,
        symbol: str,
        exchange: str,
        cost_price: float,
        volume: int,
        buy_date: str,
        notes: str = "",
        plan_pct: float | None = None,
    ) -> dict:
        validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        exch = normalize_exchange(exchange)
        if not self.get_position(symbol, exch):
            raise HTTPException(status_code=404, detail="持仓不存在")
        self.db.execute(
            text(
                """
                UPDATE app.watchlist_positions
                SET cost_price = :cost, volume = :volume, buy_date = :buy_date,
                    notes = :notes, plan_pct = :plan_pct, updated_at = :now
                WHERE user_id = CAST(:uid AS uuid) AND symbol = :symbol AND exchange = :exchange
                """
            ),
            {
                "uid": self.user_id,
                "symbol": symbol,
                "exchange": exch,
                "cost": normalize_cost_price(cost_price),
                "volume": normalize_volume(volume),
                "buy_date": buy_date[:10],
                "notes": (notes or "").strip(),
                "plan_pct": plan_pct,
                "now": _now_iso(),
            },
        )
        self.db.commit()
        row = self.get_position(symbol, exch)
        assert row is not None
        return row

    def delete_position(self, *, symbol: str, exchange: str) -> bool:
        exch = normalize_exchange(exchange)
        result = self.db.execute(
            text(
                """
                DELETE FROM app.watchlist_positions
                WHERE user_id = CAST(:uid AS uuid) AND symbol = :symbol AND exchange = :exchange
                """
            ),
            {"uid": self.user_id, "symbol": symbol, "exchange": exch},
        )
        self.db.commit()
        return bool(result.rowcount)
