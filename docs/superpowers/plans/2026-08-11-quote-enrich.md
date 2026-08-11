# 行情因子 Enrich Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `enrich_market_quotes` 做成可跑 job：Tushare `daily_basic`/`moneyflow` 因子补丁写入已有 `zak2:quote:*`，刷新换手/量比/净流入榜并 notify。

**Architecture:** 独立服务拉 Tushare → 按 TF 符号生成字段补丁 → 仅 `HSET` 已存在行情键 → 重建 `turnover_rate`/`volume_ratio`/`net_mf_amount` 榜 → `INCR seq` + `PUBLISH`。注册进 `RUNNABLE`；默认定时关（`enabled` 默认 false）。

**Tech Stack:** FastAPI/SQLAlchemy Session、Redis、Tushare（现有 client）、pytest

**Spec:** `docs/superpowers/specs/2026-08-11-quote-enrich-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*；不改 quote-collector 主循环
- 不建侧车 factor 键；不调用 `RedisQuoteWriter.write_quotes` 全量覆盖价量
- 补丁字段仅：`turnover_rate`, `volume_ratio`, `total_mv`, `circ_mv`, `net_mf_amount`
- 无 `TUSHARE_TOKEN` / 无行情键 → skipped；空补丁不 incr/publish
- 默认定时：可有 `DEFAULT_CRON` 15:20 mon-fri，但 `enabled` 默认 false
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/quote_factor_patch.py` | Redis 补丁 + 榜重建 + notify |
| `backend/app/services/ops_enrich_quotes.py` | Job：拉 Tushare、组补丁、调 patch、meta |
| `backend/app/services/ops_catalog.py` | RUNNABLE + 描述 |
| `backend/app/services/ops_runners.py` | RUNNERS |
| `backend/app/services/scheduler_defaults.py` | DEFAULT_CRON |
| `backend/tests/test_quote_factor_patch.py` | Redis mock |
| `backend/tests/test_ops_enrich_quotes.py` | Job 行为 |
| `docs/product-roadmap.md` / `docs/smoke-checklist.md` | 文档 |

---

### Task 1: Redis 因子补丁写入

**Files:**
- Create: `backend/app/services/quote_factor_patch.py`
- Test: `backend/tests/test_quote_factor_patch.py`

**Interfaces:**
- Produces: `apply_factor_patches(client, patches: dict[str, dict[str, float]]) -> dict`  
  - `patches` key = TF 符号（如 `SHSE.600519`）  
  - value = 因子字段子集（字符串化写入）  
  - 返回 `{"updated": int, "seq": int | None, "published": bool}`  
  - 仅当 `EXISTS` quote key 时 HSET；全部未命中则 updated=0 且不 incr/publish  
  - 对 `updated>0`：重建榜 `turnover_rate`（full）、`volume_ratio`/`net_mf_amount`（sparse 规则与 writer 一致：`vr>0`、`nmf!=0`），成员仅为 **本次成功补丁的 TF**（从补丁 dict 取值，不必 SCAN 全市场）  
  - 然后 `INCR` seq、`PUBLISH` notify

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import MagicMock, call

from app.core.redis_keys import META_SEQ_KEY, NOTIFY_CHANNEL, QUOTE_KEY_FMT, RANK_KEY_FMT
from app.services.quote_factor_patch import apply_factor_patches


def test_apply_skips_missing_keys_no_publish() -> None:
    client = MagicMock()
    client.exists.return_value = 0
    out = apply_factor_patches(client, {"SHSE.600519": {"turnover_rate": 1.2, "volume_ratio": 2.0}})
    assert out["updated"] == 0
    assert out["published"] is False
    client.publish.assert_not_called()
    client.incr.assert_not_called()


def test_apply_patches_existing_and_rebuilds_ranks() -> None:
    client = MagicMock()
    client.exists.return_value = 1
    client.incr.return_value = 42
    pipe = MagicMock()
    client.pipeline.return_value = pipe
    patches = {
        "SHSE.600519": {
            "turnover_rate": 1.5,
            "volume_ratio": 2.0,
            "total_mv": 100.0,
            "circ_mv": 80.0,
            "net_mf_amount": -3.0,
        }
    }
    out = apply_factor_patches(client, patches)
    assert out["updated"] == 1
    assert out["seq"] == 42
    assert out["published"] is True
    key = QUOTE_KEY_FMT.format(symbol="SHSE.600519")
    # hset called with factor fields (as strings)
    assert any(
        getattr(c, "args", None) and c.args[0] == key
        for c in pipe.method_calls
        if c[0] == "hset"
    ) or pipe.hset.called
    client.publish.assert_called_with(NOTIFY_CHANNEL, "42")
```

（实现后按真实 pipeline API 微调断言：`pipe.hset` / `pipe.delete` / `pipe.zadd` / `pipe.execute`；`incr` 可在 pipeline 外或内，与实现一致即可。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_quote_factor_patch.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `quote_factor_patch.py`**

```python
"""将 Tushare 因子补丁写入已有 zak2:quote HASH，并刷新相关榜。"""

from __future__ import annotations

from typing import Any

from app.core.redis_keys import (
    META_SEQ_KEY,
    NOTIFY_CHANNEL,
    QUOTE_KEY_FMT,
    RANK_KEY_FMT,
)

FACTOR_FIELDS = (
    "turnover_rate",
    "volume_ratio",
    "total_mv",
    "circ_mv",
    "net_mf_amount",
)


def apply_factor_patches(client: Any, patches: dict[str, dict[str, float]]) -> dict[str, Any]:
    if not patches:
        return {"updated": 0, "seq": None, "published": False}

    applied: dict[str, dict[str, float]] = {}
    for tf, fields in patches.items():
        key = QUOTE_KEY_FMT.format(symbol=tf)
        if not client.exists(key):
            continue
        mapping = {
            k: str(float(v))
            for k, v in fields.items()
            if k in FACTOR_FIELDS and v is not None
        }
        if not mapping:
            continue
        client.hset(key, mapping=mapping)
        applied[tf] = {k: float(mapping[k]) for k in mapping}

    if not applied:
        return {"updated": 0, "seq": None, "published": False}

    pipe = client.pipeline(transaction=False)
    # ranks from applied only
    for field in ("turnover_rate", "volume_ratio", "net_mf_amount"):
        pipe.delete(RANK_KEY_FMT.format(field=field))
    turn: dict[str, float] = {}
    vr: dict[str, float] = {}
    nmf: dict[str, float] = {}
    for tf, f in applied.items():
        if "turnover_rate" in f:
            turn[tf] = f["turnover_rate"]
        if f.get("volume_ratio", 0) > 0:
            vr[tf] = f["volume_ratio"]
        if f.get("net_mf_amount", 0) != 0:
            nmf[tf] = f["net_mf_amount"]
    if turn:
        pipe.zadd(RANK_KEY_FMT.format(field="turnover_rate"), turn)
    if vr:
        pipe.zadd(RANK_KEY_FMT.format(field="volume_ratio"), vr)
    if nmf:
        pipe.zadd(RANK_KEY_FMT.format(field="net_mf_amount"), nmf)
    pipe.incr(META_SEQ_KEY)
    results = pipe.execute()
    new_seq = int(results[-1])
    client.publish(NOTIFY_CHANNEL, str(new_seq))
    return {"updated": len(applied), "seq": new_seq, "published": True}
```

**注意：** 稀疏榜「仅 applied」会丢掉未在本批补丁中的旧成员。本刀可接受（spec：成员来自被补丁 TF）；若需保留全市场旧榜，改为先 `zrange` 合并——**本计划选 applied-only**，简单且与「enrich 刷新因子榜」一致。在模块 docstring 注明。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run pytest tests/test_quote_factor_patch.py -q
```

Expected: PASS（按实现微调断言后）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quote_factor_patch.py backend/tests/test_quote_factor_patch.py
git commit -m "$(cat <<'EOF'
feat(quotes): 增加 Redis 行情因子补丁写入

仅更新已有 quote 键的因子字段并刷新换手/量比/净流入榜。
EOF
)"
```

---

### Task 2: `enrich_market_quotes` Job

**Files:**
- Create: `backend/app/services/ops_enrich_quotes.py`
- Test: `backend/tests/test_ops_enrich_quotes.py`

**Interfaces:**
- Consumes: `apply_factor_patches`；`tushare_screener.fetch_daily_basic_rows` / `fetch_moneyflow_rows` / `ts_code_to_tf` / `latest_open_yyyymmdd`；`tushare_client.require_token` / `safe_float`；`get_quote_store`
- Produces: `enrich_market_quotes(db) -> dict` 含 `success`, `skipped`, `message`；并 `save_job_run_meta`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import MagicMock, patch

from app.services import ops_enrich_quotes as m


def test_enrich_skips_without_token() -> None:
    db = MagicMock()
    with patch("app.services.ops_enrich_quotes.ts.require_token", side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN")):
        out = m.enrich_market_quotes(db)
    assert out["skipped"] is True
    assert "TUSHARE" in out["message"] or "未配置" in out["message"]


def test_enrich_skips_when_redis_unavailable() -> None:
    db = MagicMock()
    store = MagicMock()
    store.meta.return_value = {"available": False}
    with patch("app.services.ops_enrich_quotes.ts.require_token", return_value="tok"), patch(
        "app.services.ops_enrich_quotes.get_quote_store", return_value=store
    ):
        out = m.enrich_market_quotes(db)
    assert out["skipped"] is True


def test_enrich_applies_patches_from_tushare() -> None:
    db = MagicMock()
    store = MagicMock()
    store.meta.return_value = {"available": True}
    client = MagicMock()
    store._conn.return_value = client  # or expose .client — match QuoteStore API
    basic = [{"ts_code": "600519.SH", "turnover_rate": 1.0, "volume_ratio": 2.0, "total_mv": 10, "circ_mv": 9}]
    flow = [{"ts_code": "600519.SH", "net_mf_amount": 5.0}]
    with patch("app.services.ops_enrich_quotes.ts.require_token", return_value="tok"), patch(
        "app.services.ops_enrich_quotes.get_quote_store", return_value=store
    ), patch("app.services.ops_enrich_quotes.latest_open_yyyymmdd", return_value="20260811"), patch(
        "app.services.ops_enrich_quotes.fetch_daily_basic_rows", return_value=basic
    ), patch("app.services.ops_enrich_quotes.fetch_moneyflow_rows", return_value=flow), patch(
        "app.services.ops_enrich_quotes.apply_factor_patches", return_value={"updated": 1, "seq": 7, "published": True}
    ) as ap, patch("app.services.ops_enrich_quotes.save_job_run_meta"):
        # Fix store connection: implementer should use a clear accessor
        out = m.enrich_market_quotes(db)
    assert out["success"] is True
    assert out.get("skipped") is not True
    assert ap.called
    patches = ap.call_args.args[1]
    assert "SHSE.600519" in patches
    assert patches["SHSE.600519"]["volume_ratio"] == 2.0
    assert patches["SHSE.600519"]["net_mf_amount"] == 5.0
```

**实现注意：** `QuoteStore` 若无公开 `client`，在 enrich 里用 `redis.Redis.from_url(get_settings().redis_url, decode_responses=True)`，或给 `QuoteStore` 增加只读 `client` property——优先 **from_url**，避免改 quotes.py 公共面（YAGNI）。测试里 patch `redis.Redis.from_url` 返回 mock client。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_ops_enrich_quotes.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现 `ops_enrich_quotes.py`**

```python
"""行情因子 enrich：Tushare → Redis quote 补丁。"""

from __future__ import annotations

from typing import Any

import redis
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.services import tushare_client as ts
from app.services.ops_scheduler import save_job_run_meta
from app.services.quote_factor_patch import apply_factor_patches
from app.services.quotes import get_quote_store
from app.services.tushare_screener import (
    fetch_daily_basic_rows,
    fetch_moneyflow_rows,
    latest_open_yyyymmdd,
    ts_code_to_tf,
)

JOB_ID = "enrich_market_quotes"


def _net_mf(item: dict[str, Any]) -> float:
    net = ts.safe_float(item.get("net_mf_amount"))
    if net == 0:
        buy = ts.safe_float(item.get("buy_lg_amount")) + ts.safe_float(item.get("buy_elg_amount"))
        sell = ts.safe_float(item.get("sell_lg_amount")) + ts.safe_float(item.get("sell_elg_amount"))
        net = buy - sell
    return net


def enrich_market_quotes(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    store = get_quote_store()
    if not store.meta().get("available"):
        message = "Redis 不可用或无行情，请先启动 quote-collector"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    trade_date = latest_open_yyyymmdd(db)
    notes: list[str] = []
    patches: dict[str, dict[str, float]] = {}

    try:
        basic_rows = fetch_daily_basic_rows(trade_date)
    except Exception as exc:  # noqa: BLE001
        basic_rows = []
        notes.append(f"daily_basic 失败: {exc}")

    for item in basic_rows:
        tf = ts_code_to_tf(str(item.get("ts_code") or ""))
        if not tf or "." not in tf:
            continue
        patches.setdefault(tf, {})
        patches[tf].update(
            {
                "turnover_rate": ts.safe_float(item.get("turnover_rate")),
                "volume_ratio": ts.safe_float(item.get("volume_ratio")),
                "total_mv": ts.safe_float(item.get("total_mv")),
                "circ_mv": ts.safe_float(item.get("circ_mv")),
            }
        )

    try:
        flow_rows = fetch_moneyflow_rows(trade_date)
    except Exception as exc:  # noqa: BLE001
        flow_rows = []
        notes.append(f"moneyflow 失败: {exc}")

    for item in flow_rows:
        tf = ts_code_to_tf(str(item.get("ts_code") or ""))
        if not tf or "." not in tf:
            continue
        patches.setdefault(tf, {})
        patches[tf]["net_mf_amount"] = _net_mf(item)

    if not patches:
        message = "无 Tushare 因子数据（可能积分不足或非交易日）"
        if notes:
            message += "；" + "；".join(notes)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    result = apply_factor_patches(client, patches)
    updated = int(result.get("updated") or 0)
    if updated <= 0:
        message = "无已存在的行情键可补丁，请先跑 quote-collector"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    message = f"已更新 {updated} 只因子（trade_date={trade_date}）"
    if notes:
        message += "；" + "；".join(notes)
    save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": message,
        "trade_date": trade_date,
        "updated": updated,
        "seq": result.get("seq"),
    }
```

调整测试：patch `redis.Redis.from_url` 而非 `store._conn`。

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/test_ops_enrich_quotes.py tests/test_quote_factor_patch.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_enrich_quotes.py backend/tests/test_ops_enrich_quotes.py
git commit -m "$(cat <<'EOF'
feat(ops): 实现 enrich_market_quotes 因子合并任务

从 Tushare 拉取换手/量比/市值/净流入并补丁写入 Redis。
EOF
)"
```

---

### Task 3: 注册 RUNNABLE + cron + 文档

**Files:**
- Modify: `backend/app/services/ops_catalog.py`
- Modify: `backend/app/services/ops_runners.py`
- Modify: `backend/app/services/scheduler_defaults.py`
- Modify: `backend/tests/test_ops_catalog.py`
- Modify: `docs/product-roadmap.md`
- Modify: `docs/smoke-checklist.md`
- Optional: `docs/superpowers/specs/2026-08-11-quote-collector-design.md` 非目标句改为指向 enrich spec

**Interfaces:**
- Produces: `enrich_market_quotes ∈ RUNNABLE_JOB_IDS`；`RUNNERS` 对齐；`DEFAULT_CRON` 含 15:20

- [ ] **Step 1: 扩展 catalog 测试**

`test_ops_catalog.py` 增加：

```python
assert "enrich_market_quotes" in RUNNABLE_JOB_IDS
```

- [ ] **Step 2: 跑测试确认可能失败**（尚未加入 RUNNABLE）

Run: `cd backend && uv run pytest tests/test_ops_catalog.py -v`  
Expected: FAIL on new assert（若先加 assert）

- [ ] **Step 3: 接线**

`RUNNABLE_JOB_IDS` 加入 `"enrich_market_quotes"`。

`JobSpec("enrich_market_quotes", ...)` 描述改为：`Tushare daily_basic/moneyflow → Redis 因子字段（Web 可跑）`。

`ops_runners.py`:

```python
from app.services import ops_enrich_quotes
# ...
"enrich_market_quotes": ops_enrich_quotes.enrich_market_quotes,
```

`scheduler_defaults.py`:

```python
"enrich_market_quotes": {"hour": 15, "minute": 20, "day_of_week": "mon-fri"},
```

文档：

- roadmap：候选 enrich 改为已完成并链 spec  
- smoke：Ops 手动跑 enrich（需 token + collector 有行情）  

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/test_ops_catalog.py tests/test_ops_job_kind.py tests/test_ops_enrich_quotes.py tests/test_quote_factor_patch.py -q
./scripts/check.sh
```

Expected: PASS；`job_kind_for("enrich_market_quotes") == "runnable"`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_catalog.py backend/app/services/ops_runners.py \
  backend/app/services/scheduler_defaults.py backend/tests/test_ops_catalog.py \
  docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
feat(ops): 注册 enrich_market_quotes 为可跑任务

默认定时 15:20 展示但开关默认关；更新路线图与 smoke。
EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| 因子补丁 + 榜 + notify | 1 |
| Job 拉 Tushare + skip 语义 | 2 |
| RUNNABLE / cron / 文档 | 3 |
| 不改 collector / 无侧车键 | 遵守 |

## 执行交接

Plan 已保存到 `docs/superpowers/plans/2026-08-11-quote-enrich.md`。
