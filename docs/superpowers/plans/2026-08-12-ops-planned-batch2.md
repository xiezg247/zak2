# Ops planned 第二批（moneyflow + 自选财报）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `prefetch_moneyflow`、`sync_watchlist_financials` 升级为可跑 job（默认定时关）。

**Architecture:** 两独立服务模块 + mock 单测；最后统一注册 RUNNABLE / RUNNERS / DEFAULT_CRON。moneyflow 薄封装复用 `fetch_moneyflow_rows`；财报在 zak2 内最小实现（2 年三表 + snapshot 纯函数），不 import vnpy/zak。

**Tech Stack:** SQLAlchemy Session、`tushare_client.query`、pytest mock

**Spec:** `docs/superpowers/specs/2026-08-12-ops-planned-batch2-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*；不实现其余 4 个 planned
- 不改 `prefetch_tushare` / enrich / team_prefetch 读路径
- 无 token / 空自选 / 空数据 → skipped + `save_job_run_meta`
- enabled 默认 false；仅加 DEFAULT_CRON
- 财报：`years=2`；仅 income / balancesheet / cashflow（无 fina_indicator）
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_prefetch_moneyflow.py` | moneyflow 薄封装 |
| `backend/app/services/ops_sync_watchlist_financials.py` | 自选三表同步 + snapshot |
| `ops_catalog` / `ops_runners` / `scheduler_defaults` | 注册 |
| `tests/test_ops_prefetch_moneyflow.py` 等 | 单测 |
| `docs/product-roadmap.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: `prefetch_moneyflow`

**Files:**
- Create: `backend/app/services/ops_prefetch_moneyflow.py`
- Create: `backend/tests/test_ops_prefetch_moneyflow.py`

**Interfaces:**
- Produces: `prefetch_moneyflow(db: Session) -> dict[str, Any]`
- Consumes: `ts.require_token`；`fetch_moneyflow_rows`；`latest_open_yyyymmdd`；`save_job_run_meta`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_prefetch_moneyflow.py
from unittest.mock import MagicMock, patch

from app.services import ops_prefetch_moneyflow as m


def test_moneyflow_skips_without_token() -> None:
    db = MagicMock()
    with patch(
        "app.services.ops_prefetch_moneyflow.ts.require_token",
        side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
    ), patch("app.services.ops_prefetch_moneyflow.save_job_run_meta") as save:
        out = m.prefetch_moneyflow(db)
    assert out["skipped"] is True
    assert out["success"] is False
    save.assert_called_once()


def test_moneyflow_upserts() -> None:
    db = MagicMock()
    rows = [{"ts_code": "000001.SZ", "net_mf_amount": 1.0}]
    with patch("app.services.ops_prefetch_moneyflow.ts.require_token", return_value="tok"), patch(
        "app.services.ops_prefetch_moneyflow.latest_open_yyyymmdd", return_value="20260811"
    ), patch(
        "app.services.ops_prefetch_moneyflow.fetch_moneyflow_rows", return_value=rows
    ), patch("app.services.ops_prefetch_moneyflow.save_job_run_meta"):
        out = m.prefetch_moneyflow(db)
    assert out["success"] is True
    assert out.get("written", 0) == 1
    assert db.execute.called
    assert db.commit.called
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_prefetch_moneyflow.py -v
```

Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
"""主力资金预拉：moneyflow → app.tushare_factor_cache。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.ops_scheduler import save_job_run_meta
from app.services.tushare_screener import fetch_moneyflow_rows, latest_open_yyyymmdd

JOB_ID = "prefetch_moneyflow"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def prefetch_moneyflow(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    trade_date = latest_open_yyyymmdd(db)
    try:
        rows = fetch_moneyflow_rows(trade_date)
    except Exception as exc:  # noqa: BLE001
        message = f"moneyflow 失败: {exc}"
        save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    if not rows:
        message = f"无 moneyflow 数据（trade_date={trade_date}）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    fetched_at = _now_iso()
    db.execute(
        text(
            """
            INSERT INTO app.tushare_factor_cache (dataset, trade_date, payload, fetched_at)
            VALUES (:dataset, :trade_date, :payload, :fetched_at)
            ON CONFLICT (dataset, trade_date) DO UPDATE SET
                payload = EXCLUDED.payload,
                fetched_at = EXCLUDED.fetched_at
            """
        ),
        {
            "dataset": "moneyflow",
            "trade_date": trade_date,
            "payload": json.dumps(rows, ensure_ascii=False),
            "fetched_at": fetched_at,
        },
    )
    db.commit()
    message = f"moneyflow 预拉 {len(rows)} 条（trade_date={trade_date}）"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": message,
        "trade_date": trade_date,
        "written": 1,
    }
```

- [ ] **Step 4: 跑测确认通过**

```bash
cd backend && uv run pytest tests/test_ops_prefetch_moneyflow.py -q
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_prefetch_moneyflow.py backend/tests/test_ops_prefetch_moneyflow.py
git commit -m "$(cat <<'EOF'
feat(ops): 实现 prefetch_moneyflow 主力资金预拉

薄封装仅写 tushare_factor_cache 的 moneyflow dataset。
EOF
)"
```

---

### Task 2: `sync_watchlist_financials`

**Files:**
- Create: `backend/app/services/ops_sync_watchlist_financials.py`
- Create: `backend/tests/test_ops_sync_watchlist_financials.py`

**Interfaces:**
- Produces: `sync_watchlist_financials(db: Session) -> dict[str, Any]`；`infer_period(end_date: str) -> str`；`compute_snapshots(ts_code: str, reports_by_type: dict[str, list[dict]]) -> list[dict]`
- Consumes: `list_watchlist_symbols`（`ops_bars_fill`）；`to_ts_code`（`bar_download`）；`ts.require_token` / `ts.query`；`save_job_run_meta`

**约定：**
- `REPORT_TYPES = ("income", "balancesheet", "cashflow")`
- `years=2` → `start_date = (today - 2*366 days).strftime("%Y%m%d")`
- 报告行规范化：`{end_date, ann_date, period, fields}`；`payload = json.dumps(fields)`
- Snapshot 字段映射对齐 zak（无 indicator → roe/gross_margin/net_margin/debt_ratio/current_ratio/roe_yoy 可为 None）
- 票间 `time.sleep(0.35)`（测试中 patch 掉）
- 至少 1 票成功 → `success=True`；有自选但 ok=0 → `success=False`；空自选 → skipped

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_sync_watchlist_financials.py
from unittest.mock import MagicMock, patch

from app.services import ops_sync_watchlist_financials as m


def test_financials_skips_empty_watchlist() -> None:
    db = MagicMock()
    with patch("app.services.ops_sync_watchlist_financials.ts.require_token", return_value="tok"), patch(
        "app.services.ops_sync_watchlist_financials.list_watchlist_symbols", return_value=[]
    ), patch("app.services.ops_sync_watchlist_financials.save_job_run_meta") as save:
        out = m.sync_watchlist_financials(db)
    assert out["skipped"] is True
    save.assert_called_once()


def test_financials_skips_without_token() -> None:
    db = MagicMock()
    with patch(
        "app.services.ops_sync_watchlist_financials.ts.require_token",
        side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
    ), patch("app.services.ops_sync_watchlist_financials.save_job_run_meta") as save:
        out = m.sync_watchlist_financials(db)
    assert out["skipped"] is True
    assert out["success"] is False
    save.assert_called_once()


def test_financials_syncs_one_symbol() -> None:
    db = MagicMock()
    income = [
        {
            "end_date": "20251231",
            "ann_date": "20260401",
            "total_revenue": 100.0,
            "n_income_attr_p": 10.0,
            "operate_profit": 12.0,
            "basic_eps": 1.0,
        }
    ]
    balance = [
        {
            "end_date": "20251231",
            "ann_date": "20260401",
            "total_assets": 1000.0,
            "total_liab": 400.0,
            "total_hldr_eqy_exc_min_int": 600.0,
        }
    ]
    cashflow = [
        {
            "end_date": "20251231",
            "ann_date": "20260401",
            "n_cashflow_act": 20.0,
            "n_cashflow_inv_act": -5.0,
            "n_cash_flows_fnc_act": -3.0,
            "c_pay_acq_const_fiolta": 2.0,
        }
    ]

    def fake_query(api_name: str, params=None, *, fields: str = ""):
        return {"income": income, "balancesheet": balance, "cashflow": cashflow}[api_name]

    with patch("app.services.ops_sync_watchlist_financials.ts.require_token", return_value="tok"), patch(
        "app.services.ops_sync_watchlist_financials.list_watchlist_symbols",
        return_value=[("000001", "SZSE")],
    ), patch("app.services.ops_sync_watchlist_financials.ts.query", side_effect=fake_query), patch(
        "app.services.ops_sync_watchlist_financials.time.sleep"
    ), patch("app.services.ops_sync_watchlist_financials.save_job_run_meta"):
        out = m.sync_watchlist_financials(db)
    assert out["success"] is True
    assert out.get("ok", 0) == 1
    assert db.execute.called
    assert db.commit.called


def test_infer_period() -> None:
    assert m.infer_period("20250331") == "Q1"
    assert m.infer_period("20250630") == "H1"
    assert m.infer_period("20250930") == "Q3"
    assert m.infer_period("20251231") == "Annual"
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_sync_watchlist_financials.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现**

实现要点（完整写入 `ops_sync_watchlist_financials.py`）：

```python
"""自选财报同步：Tushare 三表 → financial_reports / snapshots / sync_meta。"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.bar_download import to_ts_code
from app.services.ops_bars_fill import list_watchlist_symbols
from app.services.ops_scheduler import save_job_run_meta

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
    end_dt = datetime.now()
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
            round(ocf / net_income, 2) if ocf is not None and net_income not in (None, 0) else None
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


def sync_watchlist_financials(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    pool = list_watchlist_symbols(db)
    if not pool:
        message = "自选池为空"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    ok = 0
    failed = 0
    errors: list[str] = []
    for idx, (symbol, exchange) in enumerate(pool):
        try:
            _sync_one(db, symbol=symbol, exchange=exchange)
            ok += 1
        except Exception as exc:  # noqa: BLE001
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
            except Exception:  # noqa: BLE001
                db.rollback()
        if idx < len(pool) - 1:
            time.sleep(SYNC_DELAY_SECONDS)

    message = f"自选财报同步 ok={ok} failed={failed} total={len(pool)}"
    if errors:
        message += "；" + "；".join(errors[:3])
    success = ok > 0
    save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=success)
    return {
        "success": success,
        "skipped": False,
        "message": message,
        "ok": ok,
        "failed": failed,
        "total": len(pool),
    }
```

- [ ] **Step 4: 跑测确认通过**

```bash
cd backend && uv run pytest tests/test_ops_sync_watchlist_financials.py -q
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_sync_watchlist_financials.py backend/tests/test_ops_sync_watchlist_financials.py
git commit -m "$(cat <<'EOF'
feat(ops): 实现 sync_watchlist_financials 自选财报同步

近 2 年三表写入 reports/snapshots/meta，单票失败不阻断整批。
EOF
)"
```

---

### Task 3: 注册 RUNNABLE + cron + 文档 + check

**Files:**
- Modify: `backend/app/services/ops_catalog.py` — `RUNNABLE_JOB_IDS` 加两 id；更新对应 `JobSpec` description
- Modify: `backend/app/services/ops_runners.py` — import + `RUNNERS` 映射
- Modify: `backend/app/services/scheduler_defaults.py` — DEFAULT_CRON 两键
- Modify: `backend/tests/test_ops_catalog.py`、`test_ops_job_kind.py`、`test_scheduler_defaults.py`、`test_ops_job_guards.py`（planned 夹具改 `prefetch_concept_board`）
- Modify: `docs/product-roadmap.md`、`docs/smoke-checklist.md`

**Interfaces:**
- Consumes: Task 1/2 的 `prefetch_moneyflow` / `sync_watchlist_financials`
- Produces: 两 id ∈ RUNNABLE；`set(RUNNERS)==set(RUNNABLE_JOB_IDS)`；DEFAULT_CRON 有键

- [ ] **Step 1: 改注册与测试**

`RUNNABLE_JOB_IDS` 增加：
- `"prefetch_moneyflow"`
- `"sync_watchlist_financials"`

`JobSpec` 描述示例：
- moneyflow：`moneyflow → app.tushare_factor_cache（Web 可跑）`
- financials：`自选 income/balancesheet/cashflow → financial_*（Web 可跑，近 2 年）`

`RUNNERS`：
```python
"prefetch_moneyflow": ops_prefetch_moneyflow.prefetch_moneyflow,
"sync_watchlist_financials": ops_sync_watchlist_financials.sync_watchlist_financials,
```

`DEFAULT_CRON`：
```python
"prefetch_moneyflow": {"hour": 15, "minute": 35, "day_of_week": "mon-fri"},
"sync_watchlist_financials": {"hour": 9, "minute": 0, "day_of_week": "mon"},
```

`test_ops_job_kind.py` / `test_ops_job_guards.py`：凡用 `prefetch_moneyflow` 作 **planned** 夹具的，改为 `prefetch_concept_board`。

`test_ops_catalog.py`：断言两 id ∈ RUNNABLE。

`test_scheduler_defaults.py`：覆盖两 cron 键（或依赖 `test_defaults_cover_all_runnable`）。

- [ ] **Step 2: 文档**

`product-roadmap.md` 近期待办增加完成项，例如：
`6. ~~Ops planned 第二批~~（已完成 → [spec](...batch2-design.md)）：prefetch_moneyflow / sync_watchlist_financials`

`smoke-checklist.md`：
- 可跑列表加入两 job
- 手动跑检查项两条（moneyflow / 自选财报；无 token / 空自选 skipped）
- cron：moneyflow 工作日 15:35；financials 周一 09:00

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: pytest 全绿 + frontend build OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ops_catalog.py backend/app/services/ops_runners.py \
  backend/app/services/scheduler_defaults.py backend/tests/test_ops_catalog.py \
  backend/tests/test_ops_job_kind.py backend/tests/test_scheduler_defaults.py \
  backend/tests/test_ops_job_guards.py docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
feat(ops): 注册 moneyflow 与自选财报为可跑任务

DEFAULT_CRON 展示；enabled 默认关闭；更新路线图与 smoke。
EOF
)"
```

---

## Spec coverage（自审）

| Spec 要求 | Task |
|-----------|------|
| prefetch_moneyflow 薄封装 upsert | 1 |
| sync_watchlist_financials 2 年三表 + snapshot + meta | 2 |
| 单票失败不阻断 / 成功语义 | 2 |
| RUNNABLE / RUNNERS / DEFAULT_CRON / 文档 / check | 3 |
| 不实现其余 4 planned / 不改 prefetch_tushare | Global + 3 夹具改 concept |

无 TBD；类型名与 Task 1/2 Produces 一致。
