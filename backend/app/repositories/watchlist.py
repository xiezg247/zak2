from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.models.watchlist import WatchlistGroup, WatchlistGroupMember, WatchlistItem
from app.repositories.base import BaseRepository
from app.schemas.watchlist import GroupMembersBatchError, GroupMembersBatchOut
from app.services.symbols import (
    normalize_exchange,
    parse_flexible_symbol,
    parse_vt_symbol,
    to_tf_symbol,
    to_vt_symbol,
)

WATCHLIST_MAX = 50
GROUPS_MAX = 10


def resolve_symbol_pair(raw: str, exchange: str | None = None) -> tuple[str, str]:
    """把任意格式的标的输入解析为 (symbol, exchange)，供跨模块复用。"""
    if exchange:
        return raw.strip(), normalize_exchange(exchange)
    if "." in raw and raw.upper().rsplit(".", 1)[-1] in {"SSE", "SZSE", "BSE"}:
        return parse_vt_symbol(raw)
    return parse_flexible_symbol(raw)


def item_keys(item: WatchlistItem) -> dict[str, str]:
    return {
        "vt_symbol": to_vt_symbol(item.symbol, item.exchange),
        "tf_symbol": to_tf_symbol(item.symbol, item.exchange),
    }


class WatchlistItemRepository(BaseRepository[WatchlistItem]):
    """自选池条目（复合主键 symbol+exchange）。"""

    model = WatchlistItem
    order_by = (WatchlistItem.sort_order, WatchlistItem.symbol)

    def get(self, symbol: str, exchange: str) -> WatchlistItem | None:  # type: ignore[override]
        exch = normalize_exchange(exchange)
        return self.db.scalar(
            select(WatchlistItem).where(
                WatchlistItem.user_id == self.user_id,
                WatchlistItem.symbol == symbol,
                WatchlistItem.exchange == exch,
            )
        )

    def list_items(self) -> list[WatchlistItem]:
        return self.list_all()

    def add_item(
        self,
        *,
        raw_symbol: str,
        name: str = "",
        exchange: str | None = None,
    ) -> WatchlistItem:
        if exchange:
            symbol = raw_symbol.strip()
            exch = normalize_exchange(exchange)
        else:
            symbol, exch = parse_flexible_symbol(raw_symbol)

        if self.get(symbol, exch):
            raise HTTPException(status_code=409, detail="已在自选中")

        count = len(self.list_items())
        if count >= WATCHLIST_MAX:
            raise HTTPException(status_code=400, detail=f"自选已满（上限 {WATCHLIST_MAX}）")

        row = WatchlistItem(
            user_id=self.user_id,
            symbol=symbol,
            exchange=exch,
            name=name or "",
            sort_order=count,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def remove_item(self, symbol: str, exchange: str) -> bool:
        exch = normalize_exchange(exchange)
        row = self.get(symbol, exch)
        if not row:
            return False
        self.db.execute(
            delete(WatchlistGroupMember).where(
                WatchlistGroupMember.user_id == self.user_id,
                WatchlistGroupMember.symbol == symbol,
                WatchlistGroupMember.exchange == exch,
            )
        )
        self.db.delete(row)
        self.db.flush()
        remaining = self.list_items()
        for index, item in enumerate(remaining):
            item.sort_order = index
        self.db.commit()
        return True

    def reorder_items(self, vt_symbols: list[str]) -> list[WatchlistItem]:
        items = {to_vt_symbol(i.symbol, i.exchange): i for i in self.list_items()}
        ordered: list[WatchlistItem] = []
        seen: set[str] = set()
        for vt in vt_symbols:
            if vt in items and vt not in seen:
                ordered.append(items[vt])
                seen.add(vt)
        for vt, item in items.items():
            if vt not in seen:
                ordered.append(item)
        for index, item in enumerate(ordered):
            item.sort_order = index
        self.db.commit()
        return ordered


class WatchlistGroupRepository(BaseRepository[WatchlistGroup]):
    """自选分组。"""

    model = WatchlistGroup
    order_by = (WatchlistGroup.sort_order, WatchlistGroup.name)

    def list_groups(self) -> list[WatchlistGroup]:
        return self.list_all()

    def create_group(self, name: str) -> WatchlistGroup:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="分组名不能为空")
        groups = self.list_groups()
        if len(groups) >= GROUPS_MAX:
            raise HTTPException(status_code=400, detail=f"分组已满（上限 {GROUPS_MAX}）")
        if any(g.name.lower() == name.lower() for g in groups):
            raise HTTPException(status_code=409, detail="分组名已存在")
        row = WatchlistGroup(id=str(uuid4()), user_id=self.user_id, name=name, sort_order=len(groups))
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def rename_group(self, group_id: str, name: str) -> WatchlistGroup:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="分组名不能为空")
        row = self.get(group_id)
        if not row:
            raise HTTPException(status_code=404, detail="分组不存在")
        groups = self.list_groups()
        if any(g.id != group_id and g.name.lower() == name.lower() for g in groups):
            raise HTTPException(status_code=409, detail="分组名已存在")
        row.name = name
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_group(self, group_id: str) -> bool:
        row = self.get(group_id)
        if not row:
            return False
        self.db.execute(
            delete(WatchlistGroupMember).where(
                WatchlistGroupMember.user_id == self.user_id,
                WatchlistGroupMember.group_id == group_id,
            )
        )
        self.db.delete(row)
        self.db.commit()
        return True

    def reorder_groups(self, group_ids: list[str]) -> list[WatchlistGroup]:
        groups = {g.id: g for g in self.list_groups()}
        ordered: list[WatchlistGroup] = []
        seen: set[str] = set()
        for gid in group_ids:
            if gid in groups and gid not in seen:
                ordered.append(groups[gid])
                seen.add(gid)
        for gid, g in groups.items():
            if gid not in seen:
                ordered.append(g)
        for index, g in enumerate(ordered):
            g.sort_order = index
        self.db.commit()
        return ordered


class WatchlistGroupMemberRepository(BaseRepository[WatchlistGroupMember]):
    """分组成员（复合主键 group_id+symbol+exchange）。"""

    model = WatchlistGroupMember
    order_by = ()

    def _group(self, group_id: str) -> WatchlistGroup:
        group = self.db.scalar(
            select(WatchlistGroup).where(WatchlistGroup.user_id == self.user_id, WatchlistGroup.id == group_id)
        )
        if not group:
            raise HTTPException(status_code=404, detail="分组不存在")
        return group

    def list_group_members(self, group_id: str) -> list[WatchlistGroupMember]:
        return list(
            self.db.scalars(
                select(WatchlistGroupMember).where(
                    WatchlistGroupMember.user_id == self.user_id,
                    WatchlistGroupMember.group_id == group_id,
                )
            )
        )

    def add_group_member(self, group_id: str, raw_symbol: str, exchange: str | None = None) -> WatchlistGroupMember:
        self._group(group_id)
        if exchange:
            symbol, exch = raw_symbol.strip(), normalize_exchange(exchange)
        else:
            symbol, exch = parse_flexible_symbol(raw_symbol)

        # 必须已在自选池
        in_wl = self.db.scalar(
            select(WatchlistItem).where(
                WatchlistItem.user_id == self.user_id,
                WatchlistItem.symbol == symbol,
                WatchlistItem.exchange == exch,
            )
        )
        if not in_wl:
            raise HTTPException(status_code=400, detail="请先加入自选池")

        existing = self.db.scalar(
            select(WatchlistGroupMember).where(
                WatchlistGroupMember.group_id == group_id,
                WatchlistGroupMember.symbol == symbol,
                WatchlistGroupMember.exchange == exch,
            )
        )
        if existing:
            return existing

        row = WatchlistGroupMember(user_id=self.user_id, group_id=group_id, symbol=symbol, exchange=exch)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def remove_group_member(self, group_id: str, symbol: str, exchange: str) -> bool:
        exch = normalize_exchange(exchange)
        row = self.db.scalar(
            select(WatchlistGroupMember).where(
                WatchlistGroupMember.user_id == self.user_id,
                WatchlistGroupMember.group_id == group_id,
                WatchlistGroupMember.symbol == symbol,
                WatchlistGroupMember.exchange == exch,
            )
        )
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def batch_group_members(
        self,
        group_id: str,
        symbols: list[str],
        action: Literal["add", "remove"],
    ) -> GroupMembersBatchOut:
        self._group(group_id)

        added = 0
        removed = 0
        skipped = 0
        errors: list[GroupMembersBatchError] = []

        for raw in symbols:
            try:
                symbol, exch = parse_flexible_symbol(raw)
            except Exception:
                errors.append(GroupMembersBatchError(symbol=raw, detail="无法解析代码"))
                continue

            if action == "add":
                in_wl = self.db.scalar(
                    select(WatchlistItem).where(
                        WatchlistItem.user_id == self.user_id,
                        WatchlistItem.symbol == symbol,
                        WatchlistItem.exchange == exch,
                    )
                )
                if not in_wl:
                    errors.append(GroupMembersBatchError(symbol=raw, detail="请先加入自选池"))
                    continue
                existing = self.db.scalar(
                    select(WatchlistGroupMember).where(
                        WatchlistGroupMember.group_id == group_id,
                        WatchlistGroupMember.symbol == symbol,
                        WatchlistGroupMember.exchange == exch,
                    )
                )
                if existing:
                    skipped += 1
                    continue
                self.db.add(WatchlistGroupMember(user_id=self.user_id, group_id=group_id, symbol=symbol, exchange=exch))
                added += 1
            else:
                row = self.db.scalar(
                    select(WatchlistGroupMember).where(
                        WatchlistGroupMember.user_id == self.user_id,
                        WatchlistGroupMember.group_id == group_id,
                        WatchlistGroupMember.symbol == symbol,
                        WatchlistGroupMember.exchange == exch,
                    )
                )
                if not row:
                    skipped += 1
                    continue
                self.db.delete(row)
                removed += 1

        self.db.commit()
        return GroupMembersBatchOut(
            ok=True,
            action=action,
            added=added,
            removed=removed,
            skipped=skipped,
            errors=errors,
        )
