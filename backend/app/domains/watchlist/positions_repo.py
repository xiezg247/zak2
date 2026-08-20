"""自选持仓记账 CRUD（投研层，非实盘）。

ORM 操作 app.watchlist_positions（模型 WatchlistPosition，复合主键
symbol+exchange）。对外返回 PositionOut（含 vt_symbol 派生字段）；
复合主键与定制校验使其不继承 BaseRepository。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.time import china_now, china_today
from app.domains.watchlist.repository import WatchlistItemRepository
from app.domains.watchlist.schemas import PositionOut
from app.models.watchlist import WatchlistPosition
from app.services.symbols import normalize_exchange, to_vt_symbol

POSITION_MAX_ITEMS = 20
LOT_SIZE = 100
PRICE_TICK = 0.01


def _now_iso() -> str:
    return china_now().replace(microsecond=0).isoformat()


def _china_today() -> str:
    return china_today().strftime("%Y-%m-%d")


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
        raise ValidationFailed("成本价须大于 0")
    normalized = normalize_volume(volume)
    if normalized <= 0 or volume % LOT_SIZE != 0:
        raise ValidationFailed("持仓量须为 100 股整数倍")
    try:
        parsed = datetime.strptime(buy_date[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationFailed("买入日格式须为 YYYY-MM-DD") from exc
    today = china_today()
    if parsed > today:
        raise ValidationFailed("买入日不能晚于今日")


class PositionRepository:
    """持仓记账仓库（ORM 查询，返回 PositionOut）。"""

    def __init__(self, db: Session, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    def _row(self, symbol: str, exchange: str) -> WatchlistPosition | None:
        return self.db.scalar(
            select(WatchlistPosition).where(
                WatchlistPosition.user_id == self.user_id,
                WatchlistPosition.symbol == symbol,
                WatchlistPosition.exchange == exchange,
            )
        )

    @staticmethod
    def _to_out(p: WatchlistPosition) -> PositionOut:
        symbol = p.symbol
        exchange = normalize_exchange(p.exchange)
        return PositionOut(
            symbol=symbol,
            exchange=exchange,
            vt_symbol=to_vt_symbol(symbol, exchange),
            cost_price=float(p.cost_price),
            volume=int(p.volume),
            buy_date=str(p.buy_date)[:10],
            notes=str(p.notes or ""),
            source=str(p.source or "manual"),
            sort_order=int(p.sort_order or 0),
            created_at=str(p.created_at or ""),
            updated_at=str(p.updated_at or ""),
        )

    def _in_watchlist(self, symbol: str, exchange: str) -> bool:
        items = WatchlistItemRepository(self.db, self.user_id).list_items()
        exch = normalize_exchange(exchange)
        return any(i.symbol == symbol and normalize_exchange(i.exchange) == exch for i in items)

    def list_positions(self) -> list[PositionOut]:
        rows = self.db.scalars(
            select(WatchlistPosition)
            .where(WatchlistPosition.user_id == self.user_id)
            .order_by(WatchlistPosition.sort_order, WatchlistPosition.buy_date.desc())
        )
        return [self._to_out(r) for r in rows]

    def get_position(self, symbol: str, exchange: str) -> PositionOut | None:
        row = self._row(symbol, normalize_exchange(exchange))
        return self._to_out(row) if row else None

    def add_position(
        self,
        *,
        symbol: str,
        exchange: str,
        cost_price: float,
        volume: int,
        buy_date: str,
        notes: str = "",
    ) -> PositionOut:
        validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        exch = normalize_exchange(exchange)
        if not self._in_watchlist(symbol, exch):
            raise ValidationFailed("须先加入自选再录入持仓")
        if self.get_position(symbol, exch):
            raise Conflict("该标的已有持仓记录")
        count = len(self.list_positions())
        if count >= POSITION_MAX_ITEMS:
            raise ValidationFailed(f"持仓已满（上限 {POSITION_MAX_ITEMS}）")

        now = _now_iso()
        row = WatchlistPosition(
            user_id=self.user_id,
            symbol=symbol,
            exchange=exch,
            cost_price=normalize_cost_price(cost_price),
            volume=normalize_volume(volume),
            buy_date=buy_date[:10],
            notes=(notes or "").strip(),
            source="manual",
            sort_order=count,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_out(row)

    def update_position(
        self,
        *,
        symbol: str,
        exchange: str,
        cost_price: float,
        volume: int,
        buy_date: str,
        notes: str = "",
    ) -> PositionOut:
        validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        exch = normalize_exchange(exchange)
        row = self._row(symbol, exch)
        if not row:
            raise NotFound("持仓不存在")
        row.cost_price = normalize_cost_price(cost_price)
        row.volume = normalize_volume(volume)
        row.buy_date = buy_date[:10]
        row.notes = (notes or "").strip()
        row.updated_at = _now_iso()
        self.db.commit()
        self.db.refresh(row)
        return self._to_out(row)

    def delete_position(self, *, symbol: str, exchange: str) -> bool:
        row = self._row(symbol, normalize_exchange(exchange))
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
