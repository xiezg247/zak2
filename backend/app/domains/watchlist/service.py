"""自选池与分组业务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.domains.watchlist import enrich as enrich_mod
from app.domains.watchlist.repository import (
    WatchlistGroupMemberRepository,
    WatchlistGroupRepository,
    WatchlistItemRepository,
    resolve_symbol_pair,
)
from app.domains.watchlist.schemas import (
    GroupCreate,
    GroupMemberOut,
    GroupMemberRequest,
    GroupMembersBatchOut,
    GroupMembersBatchRequest,
    GroupOut,
    GroupRename,
    GroupsReorderRequest,
    WatchlistAddRequest,
    WatchlistItemOut,
    WatchlistReorderRequest,
)


def _group_out(g) -> GroupOut:
    return GroupOut(id=g.id, name=g.name, sort_order=g.sort_order)


class WatchlistService:
    @staticmethod
    def list_items(
        db: Session,
        user_id: str,
        *,
        enrich: bool,
        group_id: str | None,
    ) -> list[WatchlistItemOut]:
        items = WatchlistItemRepository(db, user_id).list_items()
        if group_id:
            members = {
                (m.symbol, m.exchange)
                for m in WatchlistGroupMemberRepository(db, user_id).list_group_members(group_id)
            }
            items = [i for i in items if (i.symbol, i.exchange) in members]
        return enrich_mod.enrich(items, with_quotes=enrich, db=db)

    @staticmethod
    def add_item(db: Session, user_id: str, body: WatchlistAddRequest) -> WatchlistItemOut:
        row = WatchlistItemRepository(db, user_id).add_item(
            raw_symbol=body.symbol, name=body.name, exchange=body.exchange
        )
        return enrich_mod.enrich([row], with_quotes=True, db=db)[0]

    @staticmethod
    def reorder(db: Session, user_id: str, body: WatchlistReorderRequest) -> list[WatchlistItemOut]:
        rows = WatchlistItemRepository(db, user_id).reorder_items(body.items)
        return enrich_mod.enrich(rows, with_quotes=False, db=db)

    @staticmethod
    def remove_item(db: Session, user_id: str, vt_symbol: str) -> None:
        symbol, exchange = resolve_symbol_pair(vt_symbol)
        if not WatchlistItemRepository(db, user_id).remove_item(symbol, exchange):
            raise NotFound("不在自选中")

    @staticmethod
    def list_groups(db: Session, user_id: str) -> list[GroupOut]:
        return [_group_out(g) for g in WatchlistGroupRepository(db, user_id).list_groups()]

    @staticmethod
    def create_group(db: Session, user_id: str, body: GroupCreate) -> GroupOut:
        g = WatchlistGroupRepository(db, user_id).create_group(body.name)
        return _group_out(g)

    @staticmethod
    def rename_group(db: Session, user_id: str, group_id: str, body: GroupRename) -> GroupOut:
        g = WatchlistGroupRepository(db, user_id).rename_group(group_id, body.name)
        return _group_out(g)

    @staticmethod
    def delete_group(db: Session, user_id: str, group_id: str) -> None:
        if not WatchlistGroupRepository(db, user_id).delete_group(group_id):
            raise NotFound("分组不存在")

    @staticmethod
    def reorder_groups(db: Session, user_id: str, body: GroupsReorderRequest) -> list[GroupOut]:
        rows = WatchlistGroupRepository(db, user_id).reorder_groups(body.group_ids)
        return [_group_out(g) for g in rows]

    @staticmethod
    def add_member(
        db: Session, user_id: str, group_id: str, body: GroupMemberRequest
    ) -> GroupMemberOut:
        row = WatchlistGroupMemberRepository(db, user_id).add_group_member(
            group_id, body.symbol, body.exchange
        )
        return GroupMemberOut(symbol=row.symbol, exchange=row.exchange)

    @staticmethod
    def batch_members(
        db: Session, user_id: str, group_id: str, body: GroupMembersBatchRequest
    ) -> GroupMembersBatchOut:
        return WatchlistGroupMemberRepository(db, user_id).batch_group_members(
            group_id, body.symbols, body.action
        )

    @staticmethod
    def remove_member(db: Session, user_id: str, group_id: str, vt_symbol: str) -> None:
        symbol, exchange = resolve_symbol_pair(vt_symbol)
        if not WatchlistGroupMemberRepository(db, user_id).remove_group_member(
            group_id, symbol, exchange
        ):
            raise NotFound("分组成员不存在")
