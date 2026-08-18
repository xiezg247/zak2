"""自选财报同步：Tushare 三表 → financial_reports / snapshots / sync_meta。"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.ops import SyncResult
from app.services.market import tushare_client as ts
from app.services.market.bar_download import to_ts_code
from app.services.ops.bars_fill import list_watchlist_symbols
from app.services.ops.scheduler import save_job_run_meta

JOB_ID = "sync_watchlist_financials"
REPORT_TYPES = ("income", "balancesheet", "cashflow")
YEARS = 2
SYNC_DELAY_SECONDS = 0.35


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def infer_period(end_date: str) -> str:
    text = str(end_date or "").strip()
    if len(text) < 8:
        return ""
    return {"0331": "Q1", "0630": "H1", "0930": "Q3", "1231": "Annual"}.get(text[4:8], text[4:8])


def _field_float(fields: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in fields or fields[key] is None or fields[key] == "":
            continue
        try:
            return float(fields[key])
        except (TypeError, ValueError):
            continue
    return None


def _prior_year_end(end_date: str) -> str | None:
    s = str(end_date or "").strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{int(s[:4]) - 1}{s[4:]}"


def _yoy(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def _normalize_rows(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in raw:
        if not isinstance(record, dict):
            continue
        end_date = str(record.get("end_date") or record.get("end_dt") or "").strip()
        if not end_date:
            continue
        ann_date = str(record.get("ann_date") or record.get("f_ann_date") or "").strip()
        fields = {str(k): v for k, v in record.items() if v is not None}
        out.append(
            {
                "end_date": end_date,
                "ann_date": ann_date,
                "period": infer_period(end_date),
                "fields": fields,
            }
        )
    out.sort(key=lambda r: str(r["end_date"]), reverse=True)
    return out


def fetch_reports_for_symbol(ts_code: str, *, years: int = YEARS) -> dict[str, list[dict[str, Any]]]:
    years = max(1, min(int(years), 15))
    end_dt = datetime.now(UTC)
    start = (end_dt - timedelta(days=years * 366)).strftime("%Y%m%d")
    end = end_dt.strftime("%Y%m%d")
    result: dict[str, list[dict[str, Any]]] = {}
    for report_type in REPORT_TYPES:
        raw = ts.query(
            report_type,
            {"ts_code": ts_code, "start_date": start, "end_date": end},
        )
        result[report_type] = _normalize_rows(raw)
    return result


def compute_snapshots(ts_code: str, reports_by_type: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    def index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {str(r["end_date"]): r for r in rows if r.get("end_date")}

    income_i = index(reports_by_type.get("income") or [])
    balance_i = index(reports_by_type.get("balancesheet") or [])
    cash_i = index(reports_by_type.get("cashflow") or [])
    end_dates = sorted(set(income_i) | set(balance_i) | set(cash_i), reverse=True)
    computed_at = _now_iso()
    snapshots: list[dict[str, Any]] = []
    for end_date in end_dates:
        income = (income_i.get(end_date) or {}).get("fields") or {}
        balance = (balance_i.get(end_date) or {}).get("fields") or {}
        cashflow = (cash_i.get(end_date) or {}).get("fields") or {}
        revenue = _field_float(income, "total_revenue", "revenue")
        net_income = _field_float(income, "n_income_attr_p", "n_income")
        operate_profit = _field_float(income, "operate_profit")
        basic_eps = _field_float(income, "basic_eps", "eps")
        total_assets = _field_float(balance, "total_assets")
        total_liab = _field_float(balance, "total_liab")
        total_equity = _field_float(balance, "total_hldr_eqy_exc_min_int", "total_hldr_eqy")
        ocf = _field_float(cashflow, "n_cashflow_act")
        icf = _field_float(cashflow, "n_cashflow_inv_act")
        fcf_flow = _field_float(cashflow, "n_cash_flows_fnc_act")
        capex = _field_float(cashflow, "c_pay_acq_const_fiolta")
        free_cashflow = round(ocf - capex, 2) if ocf is not None and capex is not None else None
        prior = _prior_year_end(end_date)
        prior_income = (income_i.get(prior or "") or {}).get("fields") or {}
        prior_revenue = _field_float(prior_income, "total_revenue", "revenue")
        prior_net = _field_float(prior_income, "n_income_attr_p", "n_income")
        ocf_to_profit = (
            round(ocf / net_income, 2) if ocf is not None and net_income is not None and net_income != 0 else None
        )
        snapshots.append(
            {
                "ts_code": ts_code,
                "end_date": end_date,
                "revenue": revenue,
                "net_income": net_income,
                "operate_profit": operate_profit,
                "basic_eps": basic_eps,
                "total_assets": total_assets,
                "total_liab": total_liab,
                "total_equity": total_equity,
                "ocf": ocf,
                "icf": icf,
                "fcf_flow": fcf_flow,
                "free_cashflow": free_cashflow,
                "roe": None,
                "gross_margin": None,
                "net_margin": None,
                "debt_ratio": None,
                "current_ratio": None,
                "revenue_yoy": _yoy(revenue, prior_revenue),
                "net_income_yoy": _yoy(net_income, prior_net),
                "roe_yoy": None,
                "ocf_to_profit": ocf_to_profit,
                "computed_at": computed_at,
            }
        )
    return snapshots


def _upsert_report(db: Session, *, ts_code: str, report_type: str, row: dict[str, Any], fetched_at: str) -> None:
    db.execute(
        text(
            """
            INSERT INTO app.financial_reports
                (ts_code, report_type, end_date, ann_date, period, source, fetched_at, payload)
            VALUES
                (:ts_code, :report_type, :end_date, :ann_date, :period, 'tushare', :fetched_at, :payload)
            ON CONFLICT (ts_code, report_type, end_date) DO UPDATE SET
                ann_date = EXCLUDED.ann_date,
                period = EXCLUDED.period,
                source = EXCLUDED.source,
                fetched_at = EXCLUDED.fetched_at,
                payload = EXCLUDED.payload
            """
        ),
        {
            "ts_code": ts_code,
            "report_type": report_type,
            "end_date": row["end_date"],
            "ann_date": row.get("ann_date") or "",
            "period": row.get("period") or "",
            "fetched_at": fetched_at,
            "payload": json.dumps(row.get("fields") or {}, ensure_ascii=False),
        },
    )


def _upsert_snapshot(db: Session, snap: dict[str, Any]) -> None:
    db.execute(
        text(
            """
            INSERT INTO app.financial_snapshots (
                ts_code, end_date, revenue, net_income, operate_profit, basic_eps,
                total_assets, total_liab, total_equity, ocf, icf, fcf_flow, free_cashflow,
                roe, gross_margin, net_margin, debt_ratio, current_ratio,
                revenue_yoy, net_income_yoy, roe_yoy, ocf_to_profit, computed_at
            ) VALUES (
                :ts_code, :end_date, :revenue, :net_income, :operate_profit, :basic_eps,
                :total_assets, :total_liab, :total_equity, :ocf, :icf, :fcf_flow, :free_cashflow,
                :roe, :gross_margin, :net_margin, :debt_ratio, :current_ratio,
                :revenue_yoy, :net_income_yoy, :roe_yoy, :ocf_to_profit, :computed_at
            )
            ON CONFLICT (ts_code, end_date) DO UPDATE SET
                revenue = EXCLUDED.revenue,
                net_income = EXCLUDED.net_income,
                operate_profit = EXCLUDED.operate_profit,
                basic_eps = EXCLUDED.basic_eps,
                total_assets = EXCLUDED.total_assets,
                total_liab = EXCLUDED.total_liab,
                total_equity = EXCLUDED.total_equity,
                ocf = EXCLUDED.ocf,
                icf = EXCLUDED.icf,
                fcf_flow = EXCLUDED.fcf_flow,
                free_cashflow = EXCLUDED.free_cashflow,
                roe = EXCLUDED.roe,
                gross_margin = EXCLUDED.gross_margin,
                net_margin = EXCLUDED.net_margin,
                debt_ratio = EXCLUDED.debt_ratio,
                current_ratio = EXCLUDED.current_ratio,
                revenue_yoy = EXCLUDED.revenue_yoy,
                net_income_yoy = EXCLUDED.net_income_yoy,
                roe_yoy = EXCLUDED.roe_yoy,
                ocf_to_profit = EXCLUDED.ocf_to_profit,
                computed_at = EXCLUDED.computed_at
            """
        ),
        snap,
    )


def _upsert_meta(
    db: Session,
    *,
    ts_code: str,
    last_sync_at: str,
    latest_end_date: str,
    latest_ann_date: str,
    sync_status: str,
    error_message: str,
    periods_count: int,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO app.financial_sync_meta (
                ts_code, last_sync_at, latest_end_date, latest_ann_date,
                sync_status, error_message, periods_count, last_access_at
            ) VALUES (
                :ts_code, :last_sync_at, :latest_end_date, :latest_ann_date,
                :sync_status, :error_message, :periods_count, :last_access_at
            )
            ON CONFLICT (ts_code) DO UPDATE SET
                last_sync_at = EXCLUDED.last_sync_at,
                latest_end_date = EXCLUDED.latest_end_date,
                latest_ann_date = EXCLUDED.latest_ann_date,
                sync_status = EXCLUDED.sync_status,
                error_message = EXCLUDED.error_message,
                periods_count = EXCLUDED.periods_count,
                last_access_at = EXCLUDED.last_access_at
            """
        ),
        {
            "ts_code": ts_code,
            "last_sync_at": last_sync_at,
            "latest_end_date": latest_end_date,
            "latest_ann_date": latest_ann_date,
            "sync_status": sync_status,
            "error_message": error_message[:500],
            "periods_count": periods_count,
            "last_access_at": last_sync_at,
        },
    )


def _sync_one(db: Session, *, symbol: str, exchange: str) -> None:
    ts_code = to_ts_code(symbol, exchange)
    fetched_at = _now_iso()
    reports = fetch_reports_for_symbol(ts_code, years=YEARS)
    for report_type, rows in reports.items():
        for row in rows:
            _upsert_report(db, ts_code=ts_code, report_type=report_type, row=row, fetched_at=fetched_at)
    snaps = compute_snapshots(ts_code, reports)
    for snap in snaps:
        _upsert_snapshot(db, snap)
    latest_end = snaps[0]["end_date"] if snaps else ""
    latest_ann = ""
    for rows in reports.values():
        for row in rows:
            if row.get("end_date") == latest_end and row.get("ann_date"):
                latest_ann = str(row["ann_date"])
                break
    periods = len({s["end_date"] for s in snaps})
    _upsert_meta(
        db,
        ts_code=ts_code,
        last_sync_at=fetched_at,
        latest_end_date=latest_end,
        latest_ann_date=latest_ann,
        sync_status="ok",
        error_message="",
        periods_count=periods,
    )
    db.commit()


def sync_watchlist_financials(db: Session) -> SyncResult:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return SyncResult(success=False, skipped=True, message=message)

    pool = list_watchlist_symbols(db)
    if not pool:
        message = "自选池为空"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return SyncResult(success=False, skipped=True, message=message)

    ok = 0
    failed = 0
    errors: list[str] = []
    for idx, (symbol, exchange) in enumerate(pool):
        try:
            _sync_one(db, symbol=symbol, exchange=exchange)
            ok += 1
        except Exception as exc:
            failed += 1
            label = to_ts_code(symbol, exchange)
            err = f"{label}: {exc}"
            errors.append(err)
            try:
                db.rollback()
                _upsert_meta(
                    db,
                    ts_code=label,
                    last_sync_at=_now_iso(),
                    latest_end_date="",
                    latest_ann_date="",
                    sync_status="error",
                    error_message=str(exc),
                    periods_count=0,
                )
                db.commit()
            except Exception:
                db.rollback()
        if idx < len(pool) - 1:
            time.sleep(SYNC_DELAY_SECONDS)

    message = f"自选财报同步 ok={ok} failed={failed} total={len(pool)}"
    if errors:
        message += "；" + "；".join(errors[:3])
    success = ok > 0
    save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=success)
    return SyncResult(
        success=success,
        message=message,
        extra={"ok": ok, "failed": failed, "total": len(pool)},
    )
