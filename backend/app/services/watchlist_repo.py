from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.watchlist import WatchlistGroup, WatchlistGroupMember, WatchlistItem
from app.services.symbols import normalize_exchange, parse_flexible_symbol, parse_vt_symbol, to_tf_symbol, to_vt_symbol

WATCHLIST_MAX = 50
GROUPS_MAX = 10


def list_items(db: Session, user_id: str) -> list[WatchlistItem]:
    return list(
        db.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.user_id == user_id)
            .order_by(WatchlistItem.sort_order, WatchlistItem.symbol)
        )
    )


def add_item(db: Session, user_id: str, *, raw_symbol: str, name: str = "", exchange: str | None = None) -> WatchlistItem:
    if exchange:
        symbol = raw_symbol.strip()
        exch = normalize_exchange(exchange)
    else:
        symbol, exch = parse_flexible_symbol(raw_symbol)

    existing = db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.symbol == symbol,
            WatchlistItem.exchange == exch,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="已在自选中")

    count = len(list_items(db, user_id))
    if count >= WATCHLIST_MAX:
        raise HTTPException(status_code=400, detail=f"自选已满（上限 {WATCHLIST_MAX}）")

    row = WatchlistItem(
        user_id=user_id,
        symbol=symbol,
        exchange=exch,
        name=name or "",
        sort_order=count,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def remove_item(db: Session, user_id: str, symbol: str, exchange: str) -> bool:
    exch = normalize_exchange(exchange)
    row = db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.symbol == symbol,
            WatchlistItem.exchange == exch,
        )
    )
    if not row:
        return False
    db.execute(
        delete(WatchlistGroupMember).where(
            WatchlistGroupMember.user_id == user_id,
            WatchlistGroupMember.symbol == symbol,
            WatchlistGroupMember.exchange == exch,
        )
    )
    db.delete(row)
    db.flush()
    remaining = list_items(db, user_id)
    for index, item in enumerate(remaining):
        item.sort_order = index
    db.commit()
    return True


def reorder_items(db: Session, user_id: str, vt_symbols: list[str]) -> list[WatchlistItem]:
    items = {to_vt_symbol(i.symbol, i.exchange): i for i in list_items(db, user_id)}
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
    db.commit()
    return ordered


def reorder_groups(db: Session, user_id: str, group_ids: list[str]) -> list[WatchlistGroup]:
    groups = {g.id: g for g in list_groups(db, user_id)}
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
    db.commit()
    return ordered


def list_groups(db: Session, user_id: str) -> list[WatchlistGroup]:
    return list(
        db.scalars(
            select(WatchlistGroup)
            .where(WatchlistGroup.user_id == user_id)
            .order_by(WatchlistGroup.sort_order, WatchlistGroup.name)
        )
    )


def create_group(db: Session, user_id: str, name: str) -> WatchlistGroup:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分组名不能为空")
    groups = list_groups(db, user_id)
    if len(groups) >= GROUPS_MAX:
        raise HTTPException(status_code=400, detail=f"分组已满（上限 {GROUPS_MAX}）")
    if any(g.name.lower() == name.lower() for g in groups):
        raise HTTPException(status_code=409, detail="分组名已存在")
    row = WatchlistGroup(id=str(uuid4()), user_id=user_id, name=name, sort_order=len(groups))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def rename_group(db: Session, user_id: str, group_id: str, name: str) -> WatchlistGroup:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分组名不能为空")
    row = db.scalar(
        select(WatchlistGroup).where(WatchlistGroup.user_id == user_id, WatchlistGroup.id == group_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="分组不存在")
    groups = list_groups(db, user_id)
    if any(g.id != group_id and g.name.lower() == name.lower() for g in groups):
        raise HTTPException(status_code=409, detail="分组名已存在")
    row.name = name
    db.commit()
    db.refresh(row)
    return row


def delete_group(db: Session, user_id: str, group_id: str) -> bool:
    row = db.scalar(
        select(WatchlistGroup).where(WatchlistGroup.user_id == user_id, WatchlistGroup.id == group_id)
    )
    if not row:
        return False
    db.execute(
        delete(WatchlistGroupMember).where(
            WatchlistGroupMember.user_id == user_id,
            WatchlistGroupMember.group_id == group_id,
        )
    )
    db.delete(row)
    db.commit()
    return True


def list_group_members(db: Session, user_id: str, group_id: str) -> list[WatchlistGroupMember]:
    return list(
        db.scalars(
            select(WatchlistGroupMember).where(
                WatchlistGroupMember.user_id == user_id,
                WatchlistGroupMember.group_id == group_id,
            )
        )
    )


def add_group_member(db: Session, user_id: str, group_id: str, raw_symbol: str, exchange: str | None = None) -> WatchlistGroupMember:
    group = db.scalar(
        select(WatchlistGroup).where(WatchlistGroup.user_id == user_id, WatchlistGroup.id == group_id)
    )
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if exchange:
        symbol, exch = raw_symbol.strip(), normalize_exchange(exchange)
    else:
        symbol, exch = parse_flexible_symbol(raw_symbol)

    # 必须已在自选池
    in_wl = db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.symbol == symbol,
            WatchlistItem.exchange == exch,
        )
    )
    if not in_wl:
        raise HTTPException(status_code=400, detail="请先加入自选池")

    existing = db.scalar(
        select(WatchlistGroupMember).where(
            WatchlistGroupMember.group_id == group_id,
            WatchlistGroupMember.symbol == symbol,
            WatchlistGroupMember.exchange == exch,
        )
    )
    if existing:
        return existing

    row = WatchlistGroupMember(user_id=user_id, group_id=group_id, symbol=symbol, exchange=exch)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def remove_group_member(db: Session, user_id: str, group_id: str, symbol: str, exchange: str) -> bool:
    exch = normalize_exchange(exchange)
    row = db.scalar(
        select(WatchlistGroupMember).where(
            WatchlistGroupMember.user_id == user_id,
            WatchlistGroupMember.group_id == group_id,
            WatchlistGroupMember.symbol == symbol,
            WatchlistGroupMember.exchange == exch,
        )
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def batch_group_members(
    db: Session,
    user_id: str,
    group_id: str,
    symbols: list[str],
    action: str,
) -> dict:
    group = db.scalar(
        select(WatchlistGroup).where(WatchlistGroup.user_id == user_id, WatchlistGroup.id == group_id)
    )
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    added = 0
    removed = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for raw in symbols:
        try:
            symbol, exch = parse_flexible_symbol(raw)
        except Exception:  # noqa: BLE001
            errors.append({"symbol": raw, "detail": "无法解析代码"})
            continue

        if action == "add":
            in_wl = db.scalar(
                select(WatchlistItem).where(
                    WatchlistItem.user_id == user_id,
                    WatchlistItem.symbol == symbol,
                    WatchlistItem.exchange == exch,
                )
            )
            if not in_wl:
                errors.append({"symbol": raw, "detail": "请先加入自选池"})
                continue
            existing = db.scalar(
                select(WatchlistGroupMember).where(
                    WatchlistGroupMember.group_id == group_id,
                    WatchlistGroupMember.symbol == symbol,
                    WatchlistGroupMember.exchange == exch,
                )
            )
            if existing:
                skipped += 1
                continue
            db.add(
                WatchlistGroupMember(
                    user_id=user_id, group_id=group_id, symbol=symbol, exchange=exch
                )
            )
            added += 1
        else:
            row = db.scalar(
                select(WatchlistGroupMember).where(
                    WatchlistGroupMember.user_id == user_id,
                    WatchlistGroupMember.group_id == group_id,
                    WatchlistGroupMember.symbol == symbol,
                    WatchlistGroupMember.exchange == exch,
                )
            )
            if not row:
                skipped += 1
                continue
            db.delete(row)
            removed += 1

    db.commit()
    return {
        "ok": True,
        "action": action,
        "added": added,
        "removed": removed,
        "skipped": skipped,
        "errors": errors,
    }


def resolve_symbol_pair(raw: str, exchange: str | None = None) -> tuple[str, str]:
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
