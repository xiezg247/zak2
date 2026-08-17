"""涨停列表本地读取与封板时间字段挂载。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.ops.sync_limit_list import sync_one_day
from app.services.seal_time import format_seal_time_label, seal_time_score
from app.services.symbols import parse_flexible_symbol, to_tf_symbol, to_vt_symbol
from app.services.tushare_screener import latest_open_yyyymmdd


def _normalize_trade_date(trade_date: str) -> str:
    return str(trade_date or "").replace("-", "")[:8]


def lookup_first_time(key: str, first_time_map: dict[str, str]) -> str:
    """按桌面键或 TickFlow 键查 first_time（map 以 TickFlow 为主）。"""
    raw = str(key or "").strip()
    if not raw or not first_time_map:
        return ""
    hit = first_time_map.get(raw)
    if hit:
        return str(hit).strip()
    try:
        code, exch = parse_flexible_symbol(raw)
        for alt in (to_tf_symbol(code, exch), to_vt_symbol(code, exch)):
            if alt == raw:
                continue
            hit = first_time_map.get(alt)
            if hit:
                return str(hit).strip()
    except ValueError:
        pass
    return ""


def _read_first_time_map(db: Session, trade_date: str) -> dict[str, str]:
    rows = db.execute(
        text(
            """
            SELECT vt_symbol, first_time
            FROM app.limit_list_daily
            WHERE trade_date = :td AND first_time <> ''
            """
        ),
        {"td": trade_date},
    ).mappings()
    result: dict[str, str] = {}
    for row in rows:
        vt = str(row.get("vt_symbol") or "").strip()
        first_time = str(row.get("first_time") or "").strip()
        if vt and first_time:
            result[vt] = first_time
    return result


def load_first_time_map(
    db: Session,
    trade_date: str | None = None,
    *,
    lazy_fetch: bool = True,
) -> dict[str, str]:
    """从 PG 读 vt_symbol → first_time；空且可懒拉时 sync 当日后再读。无 token 静默空 map。"""
    td = _normalize_trade_date(trade_date) if trade_date else latest_open_yyyymmdd(db)
    if not td:
        return {}

    try:
        result = _read_first_time_map(db, td)
    except Exception:
        result = {}

    if result or not lazy_fetch:
        return result

    try:
        ts.require_token()
    except ts.TushareNotConfiguredError:
        return {}

    try:
        sync_one_day(db, td)
        db.commit()
    except Exception:
        return {}

    try:
        return _read_first_time_map(db, td)
    except Exception:
        return {}


def attach_first_time_fields(rows: list[dict], first_time_map: dict[str, str]) -> None:
    """就地写 first_time / seal_time_score / seal_time_label；键可用桌面或 TickFlow。"""
    for row in rows:
        key = str(row.get("vt_symbol") or row.get("tf_symbol") or row.get("symbol") or "").strip()
        first_time = lookup_first_time(key, first_time_map)
        # 桌面 vt 优先时，再试 tf_symbol / symbol（与 leader pack 行兼容）
        if not first_time:
            for alt in (row.get("tf_symbol"), row.get("symbol")):
                alt_key = str(alt or "").strip()
                if alt_key and alt_key != key:
                    first_time = lookup_first_time(alt_key, first_time_map)
                    if first_time:
                        break
        row["first_time"] = first_time
        row["seal_time_score"] = seal_time_score(first_time)
        row["seal_time_label"] = format_seal_time_label(first_time)


def list_limit_list(
    db: Session,
    trade_date: str | None = None,
    *,
    lazy_fetch: bool = True,
) -> dict[str, Any]:
    """当日涨停列表摘要；无数据返回空 rows，不抛错。"""
    td = _normalize_trade_date(trade_date) if trade_date else latest_open_yyyymmdd(db)
    if not td:
        return {"trade_date": "", "total": 0, "rows": []}

    def _read_rows() -> list[dict[str, Any]]:
        rows = db.execute(
            text(
                """
                SELECT trade_date, vt_symbol, ts_code, name, limit_times,
                       first_time, last_time, fd_amount, open_times, strth, updated_at
                FROM app.limit_list_daily
                WHERE trade_date = :td
                ORDER BY limit_times DESC, first_time ASC, vt_symbol ASC
                """
            ),
            {"td": td},
        ).mappings()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            first_time = str(item.get("first_time") or "").strip()
            item["first_time"] = first_time
            item["seal_time_score"] = seal_time_score(first_time)
            item["seal_time_label"] = format_seal_time_label(first_time)
            out.append(item)
        return out

    try:
        result_rows = _read_rows()
    except Exception:
        result_rows = []

    if not result_rows and lazy_fetch:
        try:
            ts.require_token()
        except ts.TushareNotConfiguredError:
            return {"trade_date": td, "total": 0, "rows": []}
        try:
            sync_one_day(db, td)
            db.commit()
            result_rows = _read_rows()
        except Exception:
            result_rows = []

    return {"trade_date": td, "total": len(result_rows), "rows": result_rows}
