"""同步板块资金（东财行业 + 同花顺概念 → app.sector_flow_daily）。"""

from __future__ import annotations

import logging
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.schemas.ops import SyncResult
from app.domains.market import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta

logger = logging.getLogger(__name__)

JOB_ID = "sync_sector_flow_daily"


def _lookback_days() -> int:
    raw = os.getenv("SECTOR_FLOW_SYNC_DAYS", "15").strip()
    try:
        return max(1, min(int(raw), 20))
    except ValueError:
        return 15


def _to_yyyymmdd(cal_date: str) -> str:
    return cal_date.replace("-", "")[:8]


def recent_open_dates(db: Session, *, lookback: int) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT cal_date
            FROM app.trade_calendar
            WHERE is_open = 1 AND cal_date <= CURRENT_DATE::text
            ORDER BY cal_date DESC
            LIMIT :n
            """
        ),
        {"n": lookback},
    ).scalars()
    dates = [_to_yyyymmdd(str(d)) for d in rows if d]
    if dates:
        return dates
    # 无日历时降级：最近 lookback 个工作日
    from datetime import timedelta

    out: list[str] = []
    day = china_today()
    while len(out) < lookback:
        if day.weekday() < 5:
            out.append(day.strftime("%Y%m%d"))
        day -= timedelta(days=1)
    return out


def _load_sw_name_map(db: Session) -> dict[str, str]:
    """name → 申万 L2 sector_id；优先 Tushare，失败则用库内已有行业行。"""
    mapping: dict[str, str] = {}
    try:
        rows = ts.query(
            "index_classify",
            {"level": "L2", "src": "SW2021"},
            fields="index_code,industry_name",
        )
        for row in rows:
            name = str(row.get("industry_name") or "").strip()
            code = str(row.get("index_code") or "").strip()
            if name and code:
                mapping[name] = code
    except Exception:
        logger.warning("Tushare index_classify 获取失败，回退库内行业映射", exc_info=True)
    if mapping:
        return mapping
    existing = db.execute(
        text(
            """
            SELECT DISTINCT ON (name) name, sector_id
            FROM app.sector_flow_daily
            WHERE sector_kind = 'industry' AND flow_source IN ('sw_dc', 'sw')
            ORDER BY name, trade_date DESC
            """
        )
    ).mappings()
    for srow in existing:
        name = str(srow["name"] or "").strip()
        sid = str(srow["sector_id"] or "").strip()
        if name and sid:
            mapping[name] = sid
    return mapping


def _upsert_row(
    db: Session,
    *,
    trade_date: str,
    sector_kind: str,
    sector_id: str,
    name: str,
    change_pct: float,
    net_flow_yi: float,
    flow_source: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO app.sector_flow_daily
                (trade_date, sector_kind, sector_id, name, change_pct, net_flow_yi, flow_source)
            VALUES
                (:td, :kind, :sid, :name, :pct, :net, :src)
            ON CONFLICT (trade_date, sector_kind, sector_id) DO UPDATE SET
                name = EXCLUDED.name,
                change_pct = EXCLUDED.change_pct,
                net_flow_yi = EXCLUDED.net_flow_yi,
                flow_source = EXCLUDED.flow_source
            """
        ),
        {
            "td": trade_date,
            "kind": sector_kind,
            "sid": sector_id,
            "name": name,
            "pct": change_pct,
            "net": net_flow_yi,
            "src": flow_source,
        },
    )


def _sync_one_day(db: Session, trade_date: str, sw_map: dict[str, str]) -> str | None:
    parts: list[str] = []

    try:
        dc_rows = ts.query(
            "moneyflow_ind_dc",
            {"trade_date": trade_date, "content_type": "行业"},
            fields="trade_date,content_type,ts_code,name,pct_change,net_amount",
        )
    except Exception:
        dc_rows = []

    industry_n = 0
    for row in dc_rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        sector_id = sw_map.get(name)
        if not sector_id:
            continue
        _upsert_row(
            db,
            trade_date=trade_date,
            sector_kind="industry",
            sector_id=sector_id,
            name=name,
            change_pct=round(ts.safe_float(row.get("pct_change")), 2),
            net_flow_yi=round(ts.safe_float(row.get("net_amount")) / 1e8, 2),
            flow_source="sw_dc",
        )
        industry_n += 1
    if industry_n:
        parts.append(f"行业{industry_n}")

    try:
        ths_rows = ts.query(
            "moneyflow_cnt_ths",
            {"trade_date": trade_date},
            fields="trade_date,ts_code,name,pct_change,net_amount",
        )
    except Exception:
        ths_rows = []

    concept_n = 0
    if ths_rows:
        for row in ths_rows:
            name = str(row.get("name") or "").strip()
            sector_id = str(row.get("ts_code") or name).strip()
            if not name or not sector_id:
                continue
            _upsert_row(
                db,
                trade_date=trade_date,
                sector_kind="concept",
                sector_id=sector_id,
                name=name,
                change_pct=round(ts.safe_float(row.get("pct_change")), 2),
                net_flow_yi=round(ts.safe_float(row.get("net_amount")), 2),
                flow_source="ths_concept",
            )
            concept_n += 1
        if concept_n:
            parts.append(f"概念{concept_n}")
    else:
        try:
            dc_concept = ts.query(
                "moneyflow_ind_dc",
                {"trade_date": trade_date, "content_type": "概念"},
                fields="trade_date,content_type,ts_code,name,pct_change,net_amount",
            )
        except Exception:
            dc_concept = []
        for row in dc_concept:
            name = str(row.get("name") or "").strip()
            sector_id = str(row.get("ts_code") or name).strip()
            if not name or not sector_id:
                continue
            _upsert_row(
                db,
                trade_date=trade_date,
                sector_kind="concept",
                sector_id=sector_id,
                name=name,
                change_pct=round(ts.safe_float(row.get("pct_change")), 2),
                net_flow_yi=round(ts.safe_float(row.get("net_amount")) / 1e8, 2),
                flow_source="dc_concept",
            )
            concept_n += 1
        if concept_n:
            parts.append(f"概念东财{concept_n}")

    if not parts:
        return None
    return f"{trade_date}:{'/'.join(parts)}"


def sync_sector_flow_daily(db: Session) -> SyncResult:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return SyncResult(success=False, message=message, skipped=True, extra={"days": 0})

    lookback = _lookback_days()
    dates = recent_open_dates(db, lookback=lookback)
    sw_map = _load_sw_name_map(db)
    summaries: list[str] = []
    for trade_date in dates:
        summary = _sync_one_day(db, trade_date, sw_map)
        if summary:
            summaries.append(summary)
    db.commit()

    if not summaries:
        message = "未同步到板块资金数据（可能非交易日、Tushare 尚未更新或权限不足）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return SyncResult(success=False, message=message, extra={"days": 0})

    message = "板块资金同步 " + "，".join(summaries[:8])
    if len(summaries) > 8:
        message += f" …共{len(summaries)}日"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return SyncResult(success=True, message=message, extra={"days": len(summaries)})
