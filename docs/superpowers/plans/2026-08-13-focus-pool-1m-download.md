# 关注池 1m K 真下载 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tushare `stk_mins` 写入 `dbbardata`（1m）；升级 `fill_focus_pool_minute` 真下载。

**Architecture:** 扩展 `bar_download`（fetch/upsert/overview interval）；fill job 对自选池按 overview 增量拉最近 N 交易日；env 可配置 lookback/max。

**Tech Stack:** FastAPI、SQLAlchemy、Tushare HTTP、pytest

**Spec:** `docs/superpowers/specs/2026-08-13-focus-pool-1m-download-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不引入 arq/Celery；不默认开定时；不做全市场/其它分钟周期
- 无 token → skipped；message 不得含「1m 下载未接入」
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/bar_download.py` | 1m fetch/upsert；overview 支持 interval |
| `backend/tests/test_bar_download_minute.py` | 1m 单测 |
| `backend/app/services/ops_fill_focus_pool_minute.py` | 真下载 job |
| `backend/tests/test_ops_fill_focus_pool_minute.py` | job 测 |
| `backend/app/services/ops_catalog.py` | 描述 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | #30 |

---

### Task 1: `bar_download` 1m 能力

**Files:**
- Modify: `backend/app/services/bar_download.py`
- Create: `backend/tests/test_bar_download_minute.py`

**Interfaces:**
- Produces: `INTERVAL_1M = "1m"`
- Produces: `refresh_overview(db, *, symbol, exchange, interval=INTERVAL_DAILY)`
- Produces: `fetch_minute_rows(*, ts_code, start: datetime, end: datetime) -> list[dict]`
- Produces: `upsert_minute_bars(db, *, symbol, exchange, rows) -> int`
- Produces: `download_minute_bars(db, *, symbol, exchange, start: date, end: date) -> int`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_bar_download_minute.py
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.services import bar_download as bars


def test_fetch_minute_rows_calls_stk_mins() -> None:
    with patch.object(bars.ts, "query", return_value=[]) as q:
        bars.fetch_minute_rows(
            ts_code="600519.SH",
            start=datetime(2026, 8, 11, 9, 0, 0),
            end=datetime(2026, 8, 13, 19, 0, 0),
        )
    assert q.call_args.args[0] == "stk_mins"
    params = q.call_args.args[1]
    assert params["freq"] == "1min"
    assert "600519.SH" in params["ts_code"]
    assert "09:00:00" in params["start_date"]


def test_upsert_minute_bars_writes_and_refreshes() -> None:
    db = MagicMock()
    rows = [
        {
            "trade_time": "2026-08-13 09:31:00",
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.05,
            "vol": 100,
            "amount": 1000,
        }
    ]
    with patch.object(bars, "refresh_overview") as ref:
        n = bars.upsert_minute_bars(db, symbol="600519", exchange="SSE", rows=rows)
    assert n == 1
    assert db.execute.call_count >= 2  # delete + insert
    ref.assert_called_once()
    assert ref.call_args.kwargs.get("interval") == bars.INTERVAL_1M


def test_refresh_overview_accepts_interval() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.first.return_value = {
        "start_dt": datetime(2026, 8, 1),
        "end_dt": datetime(2026, 8, 13),
        "n": 10,
    }
    bars.refresh_overview(db, symbol="600519", exchange="SSE", interval="1m")
    # 至少一次 SQL 绑定含 interval 1m
    found = False
    for c in db.execute.call_args_list:
        params = c.args[1] if len(c.args) > 1 else c.kwargs.get("parameters") or {}
        if isinstance(params, dict) and params.get("iv") == "1m":
            found = True
            break
    assert found
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_bar_download_minute.py -q
```

Expected: FAIL

- [ ] **Step 3: 实现**

在 `bar_download.py`：

1. 增加 `INTERVAL_1M = "1m"`。  
2. 改 `refresh_overview` 增加 `interval: str = INTERVAL_DAILY`，所有 SQL 用 `:iv` 绑定该参数（日 K `upsert_daily_bars` 仍默认）。  
3. 实现：

```python
def fetch_minute_rows(*, ts_code: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    return ts.query(
        "stk_mins",
        {
            "ts_code": ts_code,
            "freq": "1min",
            "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
        },
        fields="ts_code,trade_time,open,high,low,close,vol,amount",
    )


def _parse_trade_time(raw: Any) -> datetime | None:
    text_v = str(raw or "").strip()
    if not text_v:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text_v[:19] if fmt.startswith("%Y-%") else text_v[:14], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text_v.replace("Z", ""))
    except ValueError:
        return None


def upsert_minute_bars(db: Session, *, symbol: str, exchange: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    exch = normalize_exchange(exchange)
    written = 0
    for row in rows:
        dt = _parse_trade_time(row.get("trade_time"))
        if dt is None:
            continue
        db.execute(
            text(
                """
                DELETE FROM public.dbbardata
                WHERE symbol = :s AND exchange = :e AND interval = :iv AND datetime = :dt
                """
            ),
            {"s": symbol, "e": exch, "iv": INTERVAL_1M, "dt": dt},
        )
        db.execute(
            text(
                """
                INSERT INTO public.dbbardata (
                    symbol, exchange, datetime, interval,
                    volume, turnover, open_interest,
                    open_price, high_price, low_price, close_price
                ) VALUES (
                    :s, :e, :dt, :iv,
                    :vol, :amt, 0,
                    :o, :h, :l, :c
                )
                """
            ),
            {
                "s": symbol,
                "e": exch,
                "dt": dt,
                "iv": INTERVAL_1M,
                "vol": ts.safe_float(row.get("vol")),
                "amt": ts.safe_float(row.get("amount")),
                "o": ts.safe_float(row.get("open")),
                "h": ts.safe_float(row.get("high")),
                "l": ts.safe_float(row.get("low")),
                "c": ts.safe_float(row.get("close")),
            },
        )
        written += 1
    if written:
        refresh_overview(db, symbol=symbol, exchange=exch, interval=INTERVAL_1M)
    return written


def download_minute_bars(
    db: Session,
    *,
    symbol: str,
    exchange: str,
    start: date,
    end: date,
) -> int:
    if start > end:
        return 0
    ts_code = to_ts_code(symbol, exchange)
    start_dt = datetime(start.year, start.month, start.day, 9, 0, 0)
    end_dt = datetime(end.year, end.month, end.day, 19, 0, 0)
    rows = fetch_minute_rows(ts_code=ts_code, start=start_dt, end=end_dt)
    return upsert_minute_bars(db, symbol=symbol, exchange=exchange, rows=rows)
```

- [ ] **Step 4: 跑测通过（含日 K 相关回归）**

```bash
cd backend && uv run pytest tests/test_bar_download_minute.py tests/test_bars_fill.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bar_download.py backend/tests/test_bar_download_minute.py
git commit -m "$(cat <<'EOF'
feat(bars): 支持 Tushare 1m K 下载写入 dbbardata

stk_mins 拉取；overview 可按 interval 刷新。
EOF
)"
```

---

### Task 2: 升级 `fill_focus_pool_minute`

**Files:**
- Modify: `backend/app/services/ops_fill_focus_pool_minute.py`
- Modify: `backend/app/services/ops_catalog.py`
- Modify: `backend/tests/test_ops_fill_focus_pool_minute.py`

**Interfaces:**
- Consumes: `bar_download.download_minute_bars` / `get_overview_row`（需支持 1m 或专用查询）
- Consumes: `ops_sync_sector.recent_open_dates` 或等价日历查询
- Produces: 返回含 `downloaded`, `bars_added`, `failed`, `lookback_days`, `max_symbols`

- [ ] **Step 1: 重写测试**

```python
# backend/tests/test_ops_fill_focus_pool_minute.py
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from app.services import ops_fill_focus_pool_minute as m
from app.services import tushare_client as ts


def test_minute_skips_without_token() -> None:
    db = MagicMock()
    with (
        patch.object(m.ts, "require_token", side_effect=ts.TushareNotConfiguredError("未配置")),
        patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta") as save,
    ):
        out = m.fill_focus_pool_minute(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "未接入" not in out["message"]
    assert save.call_args.kwargs["last_success"] is False


def test_minute_downloads() -> None:
    db = MagicMock()
    pool = [("600519", "SSE")]
    with (
        patch.object(m.ts, "require_token", return_value="t"),
        patch.object(m, "list_watchlist_symbols", return_value=pool),
        patch.object(m, "_lookback_days", return_value=5),
        patch.object(m, "_max_symbols", return_value=50),
        patch.object(m, "_open_date_window", return_value=(date(2026, 8, 7), date(2026, 8, 13))),
        patch.object(m, "_needs_1m_download", return_value=True),
        patch.object(m, "download_minute_bars", return_value=100) as dl,
        patch.object(m, "_count_overview", side_effect=[1, 1]),
        patch.object(m, "_sleep", return_value=None),
        patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta") as save,
    ):
        out = m.fill_focus_pool_minute(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["downloaded"] == 1
    assert out["bars_added"] == 100
    assert "未接入" not in out["message"]
    dl.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_minute_empty_pool_ok() -> None:
    db = MagicMock()
    with (
        patch.object(m.ts, "require_token", return_value="t"),
        patch.object(m, "list_watchlist_symbols", return_value=[]),
        patch.object(m, "_lookback_days", return_value=5),
        patch.object(m, "_max_symbols", return_value=50),
        patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta"),
    ):
        out = m.fill_focus_pool_minute(db)
    assert out["success"] is True
    assert out["pool_size"] == 0
    assert out["downloaded"] == 0
    assert "未接入" not in out["message"]
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_fill_focus_pool_minute.py -q
```

Expected: FAIL（旧断言/旧行为）

- [ ] **Step 3: 实现 job**

```python
# ops_fill_focus_pool_minute.py 要点
import os
import time
from datetime import date, datetime

from app.services import bar_download as bars
from app.services import tushare_client as ts
from app.services.ops_bars_fill import list_watchlist_symbols
from app.services.ops_sync_sector import recent_open_dates  # yyyymmdd list
from app.services.bar_download import INTERVAL_1M, download_minute_bars, get_overview_row
# 注意：get_overview_row 当前写死 INTERVAL_DAILY — Task 2 需给 get_overview_row 增加 interval 参数
# 或在本文件写 _get_1m_overview 查询。优先扩展 get_overview_row(..., interval=INTERVAL_DAILY)。

JOB_ID = "fill_focus_pool_minute"


def _lookback_days() -> int:
    ...


def _max_symbols() -> int:
    ...


def _sleep() -> None:
    # 读 BARS_FILL_SLEEP_SEC，默认 0.05
    ...


def _open_date_window(db: Session) -> tuple[date, date]:
    ymds = recent_open_dates(db, lookback=_lookback_days())
    # ymds 新→旧；转 date；start=min end=max
    ...


def _needs_1m_download(db, symbol, exchange, *, as_of: date) -> bool:
    row = get_overview_row(db, symbol=symbol, exchange=exchange, interval=INTERVAL_1M)
    if not row:
        return True
    return bars.is_stale_end(row.get("end"), as_of=as_of)


def fill_focus_pool_minute(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        msg = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=msg, last_success=False)
        return {"success": False, "skipped": True, "message": msg, ...zeros...}

    max_n = _max_symbols()
    lookback = _lookback_days()
    pool = list_watchlist_symbols(db)[:max_n]
    start_d, end_d = _open_date_window(db)
    as_of = end_d
    downloaded = 0
    bars_added = 0
    failed: list[str] = []
    for symbol, exchange in pool:
        if not _needs_1m_download(db, symbol, exchange, as_of=as_of):
            continue
        try:
            n = download_minute_bars(db, symbol=symbol, exchange=exchange, start=start_d, end=end_d)
            db.commit()
            downloaded += 1
            bars_added += n
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed.append(f"{symbol}.{exchange}:{exc}")
        _sleep()

    with_daily = _count_overview(db, pool, interval="d") if pool else 0
    with_1m = _count_overview(db, pool, interval="1m") if pool else 0
    msg = (
        f"关注池 1m：pool={len(pool)} downloaded={downloaded} bars={bars_added} "
        f"failed={len(failed)} lookback={lookback} "
        f"daily={with_daily} 1m={with_1m} missing_1m={len(pool)-with_1m}"
    )
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {...}
```

**Task 1 若未改 `get_overview_row`：** 在 Task 2 一并给 `get_overview_row` 增加 `interval` 默认 `d`（小改动，属本 job 需要）。

catalog：`自选关注池 1m K 增量下载 → dbbardata（Web 可跑）`。

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_ops_fill_focus_pool_minute.py tests/test_bar_download_minute.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_fill_focus_pool_minute.py \
  backend/app/services/ops_catalog.py \
  backend/app/services/bar_download.py \
  backend/tests/test_ops_fill_focus_pool_minute.py
git commit -m "$(cat <<'EOF'
feat(ops): fill_focus_pool_minute 真下载自选 1m K

可配置 lookback/max；无 token 诚实 skipped。
EOF
)"
```

（若 `get_overview_row` 改动已在 Task 1 commit，则本步可不重复 add `bar_download.py`。）

---

### Task 3: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

替换：

```markdown
- [ ] Ops 手动跑 **`fill_focus_pool_minute`**（需 `TUSHARE_TOKEN` + 分钟权限；可下载自选 1m；无 token 可 skipped）；文案无「1m 下载未接入」；成功后 `bars?interval=1m` 或 overview 可见
```

- [ ] **Step 2: roadmap**

```markdown
30. ~~关注池 1m K 真下载~~（已完成 → [spec](./superpowers/specs/2026-08-13-focus-pool-1m-download-design.md)）
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: `OK：测试与构建通过`

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 记录关注池 1m K 真下载完成

更新 smoke 与路线图 #30。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| §1 bar_download 1m | 1 |
| §2 fill job | 2 |
| §3 测试 | 1–2 |
| §4–5 文档/验收 | 3 |
| 可配置 lookback/max | 2 |
| 无「未接入」文案 | 2–3 |

无 TBD。`get_overview_row` 须支持 `interval`（Task 1 或 Task 2）。
