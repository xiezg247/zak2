"""当日停牌 vt 集合（读 app.symbol_suspend_days）。"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.symbols import to_vt_symbol
from app.services.tushare_screener import latest_open_yyyymmdd


def resolve_suspend_cal_date(db: Session) -> str:
    ymd = latest_open_yyyymmdd(db)
    s = str(ymd or "").replace("-", "")[:8]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def load_suspended_vt_symbols(db: Session, cal_date: str | None = None) -> set[str]:
    day = cal_date or resolve_suspend_cal_date(db)
    rows = (
        db.execute(
            text(
                """
            SELECT symbol, exchange
            FROM app.symbol_suspend_days
            WHERE cal_date = :d
            """
            ),
            {"d": day},
        )
        .mappings()
        .all()
    )
    out: set[str] = set()
    for r in rows:
        sym = str(r.get("symbol") or "").strip()
        exch = str(r.get("exchange") or "").strip()
        if sym and exch:
            out.add(to_vt_symbol(sym, exch))
    return out
