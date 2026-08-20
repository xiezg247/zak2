from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.domains.content.schemas import NoteEntryOut, NoteMemoOut, NoteSymbolOut
from app.models.content import StockNoteEntry, StockNoteMemo
from app.repositories.pagination import Page, paginate
from app.repositories.watchlist import resolve_symbol_pair
from app.services.symbols import to_vt_symbol


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def list_note_symbols(db: Session, user_id: str) -> list[NoteSymbolOut]:
    memos = list(db.scalars(select(StockNoteMemo).where(StockNoteMemo.user_id == user_id)))
    entry_counts = {
        (s, e): int(c)
        for s, e, c in db.execute(
            select(StockNoteEntry.symbol, StockNoteEntry.exchange, func.count())
            .where(StockNoteEntry.user_id == user_id)
            .group_by(StockNoteEntry.symbol, StockNoteEntry.exchange)
        ).all()
    }
    keys: set[tuple[str, str]] = {(m.symbol, m.exchange) for m in memos}
    keys |= set(entry_counts)
    memo_map = {(m.symbol, m.exchange): m for m in memos}
    out: list[NoteSymbolOut] = []
    for symbol, exchange in keys:
        memo = memo_map.get((symbol, exchange))
        count = entry_counts.get((symbol, exchange), 0)
        preview = (memo.body or "").strip().replace("\n", " ")[:80] if memo else ""
        updated = memo.updated_at if memo else ""
        out.append(
            NoteSymbolOut(
                symbol=symbol,
                exchange=exchange,
                vt_symbol=to_vt_symbol(symbol, exchange),
                memo_preview=preview,
                entry_count=count,
                updated_at=updated,
            )
        )
    out.sort(key=lambda x: x.updated_at or "", reverse=True)
    return out


def get_memo(db: Session, user_id: str, raw: str) -> NoteMemoOut:
    symbol, exchange = resolve_symbol_pair(raw)
    row = db.scalar(
        select(StockNoteMemo).where(
            StockNoteMemo.user_id == user_id,
            StockNoteMemo.symbol == symbol,
            StockNoteMemo.exchange == exchange,
        )
    )
    return NoteMemoOut(
        symbol=symbol,
        exchange=exchange,
        vt_symbol=to_vt_symbol(symbol, exchange),
        body=row.body if row else "",
        updated_at=row.updated_at if row else "",
    )


def upsert_memo(db: Session, user_id: str, raw: str, body: str) -> NoteMemoOut:
    symbol, exchange = resolve_symbol_pair(raw)
    row = db.scalar(
        select(StockNoteMemo).where(
            StockNoteMemo.user_id == user_id,
            StockNoteMemo.symbol == symbol,
            StockNoteMemo.exchange == exchange,
        )
    )
    now = _now()
    if row:
        row.body = body
        row.updated_at = now
    else:
        row = StockNoteMemo(user_id=user_id, symbol=symbol, exchange=exchange, body=body, updated_at=now)
        db.add(row)
    db.commit()
    db.refresh(row)
    return NoteMemoOut(
        symbol=row.symbol,
        exchange=row.exchange,
        vt_symbol=to_vt_symbol(row.symbol, row.exchange),
        body=row.body,
        updated_at=row.updated_at,
    )


def _entry_out(r: StockNoteEntry) -> NoteEntryOut:
    return NoteEntryOut(
        id=int(r.id),
        symbol=r.symbol,
        exchange=r.exchange,
        vt_symbol=to_vt_symbol(r.symbol, r.exchange),
        body=r.body,
        created_at=r.created_at,
    )


def list_entries(db: Session, user_id: str, raw: str, *, limit: int = 100) -> list[NoteEntryOut]:
    symbol, exchange = resolve_symbol_pair(raw)
    rows = db.scalars(
        select(StockNoteEntry)
        .where(
            StockNoteEntry.user_id == user_id,
            StockNoteEntry.symbol == symbol,
            StockNoteEntry.exchange == exchange,
        )
        .order_by(desc(StockNoteEntry.created_at), desc(StockNoteEntry.id))
        .limit(limit)
    )
    return [_entry_out(r) for r in rows]


def list_entries_page(
    db: Session,
    user_id: str,
    raw: str,
    *,
    page: int = 1,
    page_size: int = 50,
) -> Page[NoteEntryOut]:
    symbol, exchange = resolve_symbol_pair(raw)
    stmt = (
        select(StockNoteEntry)
        .where(
            StockNoteEntry.user_id == user_id,
            StockNoteEntry.symbol == symbol,
            StockNoteEntry.exchange == exchange,
        )
        .order_by(desc(StockNoteEntry.created_at), desc(StockNoteEntry.id))
    )
    result = paginate(db, stmt, page=page, page_size=page_size)
    return result.map(_entry_out)


def add_entry(db: Session, user_id: str, raw: str, body: str) -> NoteEntryOut:
    body = body.strip()
    if not body:
        raise ValidationFailed("内容不能为空")
    symbol, exchange = resolve_symbol_pair(raw)
    row = StockNoteEntry(
        user_id=user_id,
        symbol=symbol,
        exchange=exchange,
        body=body,
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return NoteEntryOut(
        id=int(row.id),
        symbol=row.symbol,
        exchange=row.exchange,
        vt_symbol=to_vt_symbol(row.symbol, row.exchange),
        body=row.body,
        created_at=row.created_at,
    )


def delete_entry(db: Session, user_id: str, entry_id: int) -> bool:
    row = db.scalar(select(StockNoteEntry).where(StockNoteEntry.id == entry_id, StockNoteEntry.user_id == user_id))
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
