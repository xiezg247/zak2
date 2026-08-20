"""持仓记账业务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.domains.watchlist.positions_repo import PositionRepository
from app.domains.watchlist.repository import resolve_symbol_pair
from app.domains.watchlist.schemas import PositionOut, PositionUpsertRequest


class PositionsService:
    @staticmethod
    def list(db: Session, user_id: str) -> list[PositionOut]:
        return PositionRepository(db, user_id).list_positions()

    @staticmethod
    def add(db: Session, user_id: str, body: PositionUpsertRequest) -> PositionOut:
        symbol, exchange = resolve_symbol_pair(body.symbol, body.exchange)
        return PositionRepository(db, user_id).add_position(
            symbol=symbol,
            exchange=exchange,
            cost_price=body.cost_price,
            volume=body.volume,
            buy_date=body.buy_date,
            notes=body.notes,
        )

    @staticmethod
    def update(db: Session, user_id: str, vt_symbol: str, body: PositionUpsertRequest) -> PositionOut:
        symbol, exchange = resolve_symbol_pair(vt_symbol)
        return PositionRepository(db, user_id).update_position(
            symbol=symbol,
            exchange=exchange,
            cost_price=body.cost_price,
            volume=body.volume,
            buy_date=body.buy_date,
            notes=body.notes,
        )

    @staticmethod
    def delete(db: Session, user_id: str, vt_symbol: str) -> None:
        symbol, exchange = resolve_symbol_pair(vt_symbol)
        if not PositionRepository(db, user_id).delete_position(symbol=symbol, exchange=exchange):
            raise NotFound("持仓不存在")
