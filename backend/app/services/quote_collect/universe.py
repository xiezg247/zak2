"""从 app.universe 加载 TickFlow 符号。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.bar_download import list_universe_symbols
from app.services.symbols import to_tf_symbol


def load_tf_symbols(db: Session) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for symbol, exchange in list_universe_symbols(db):
        tf = to_tf_symbol(symbol, exchange)
        if tf in seen:
            continue
        seen.add(tf)
        out.append(tf)
    return out
