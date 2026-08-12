# Ops 三 skipped job 薄做实 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 做实 `warm_watchlist_strategy_cache` / `prefetch_concept_board` / `fill_focus_pool_minute`（薄副作用，不再恒 skipped）。

**Architecture:** 策略 Redis→PG 桥；概念委托 `sync_sector_flow_daily`；1m 对自选池盘点 `dbbaroverview`。沿用 APScheduler + RUNNERS，不引入 arq/Celery。

**Tech Stack:** FastAPI、SQLAlchemy、Redis、pytest

**Spec:** `docs/superpowers/specs/2026-08-12-ops-skipped-jobs-thin-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不引入 arq / Celery；不跑策略引擎；不下载 1m；不建 ths_member
- 策略/1m：无数据仍 `success=True, skipped=False`；概念透传 sector sync（无 token → skipped）
- DEFAULT_CRON / enabled 默认 false 不变
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_warm_watchlist_strategy.py` | Redis→PG 桥 |
| `backend/app/services/ops_prefetch_concept_board.py` | 委托 sector sync |
| `backend/app/services/ops_fill_focus_pool_minute.py` | 自选池 d/1m 盘点 |
| `backend/app/services/ops_catalog.py` | 三 job 描述 |
| `backend/tests/test_ops_warm_watchlist_strategy.py` | 策略测 |
| `backend/tests/test_ops_prefetch_concept_board.py` | 概念测 |
| `backend/tests/test_ops_fill_focus_pool_minute.py` | 1m 盘点测 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 #27 |

---

### Task 1: 做实 `warm_watchlist_strategy_cache`

**Files:**
- Modify: `backend/app/services/ops_warm_watchlist_strategy.py`
- Modify: `backend/app/services/ops_catalog.py`（本 job 描述）
- Modify: `backend/tests/test_ops_warm_watchlist_strategy.py`

**Interfaces:**
- Produces: `warm_watchlist_strategy_cache(db) -> {success, skipped: False, message, written_signals, written_positions}`
- Consumes: Redis（`KEY_PREFIX`）、`save_job_run_meta`、`strategy_board.DEFAULT_CONFIG_KEY` / `_parse_payload` 可选复用

- [ ] **Step 1: 重写测试**

```python
# backend/tests/test_ops_warm_watchlist_strategy.py
from unittest.mock import MagicMock, patch

from app.services import ops_warm_watchlist_strategy as m


def test_warm_bridges_redis_signals() -> None:
    db = MagicMock()
    fake_client = MagicMock()
    # scan yields one signal key; get returns envelope JSON
    signal_key = b"zak2:cache:signal:latest:AshareShortBreakoutStrategy:5:10:600519.SSE"
    fake_client.scan_iter.side_effect = lambda **kw: (
        iter([signal_key])
        if "signal:latest" in kw.get("match", "")
        else iter([])
    )
    fake_client.get.return_value = (
        b'{"payload":"{\\"signal\\":\\"buy\\",\\"vt_symbol\\":\\"600519.SSE\\"}",'
        b'"bar_as_of":"2026-08-12","updated_at":"2026-08-12T10:00:00+08:00"}'
    )
    with (
        patch.object(m, "_redis_client", return_value=fake_client),
        patch.object(m, "_list_config_keys", return_value=["AshareShortBreakoutStrategy:5:10"]),
        patch.object(m, "_upsert_signal") as up_sig,
        patch.object(m, "_upsert_position") as up_pos,
        patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta") as save,
    ):
        out = m.warm_watchlist_strategy_cache(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert out["written_signals"] == 1
    assert out["written_positions"] == 0
    up_sig.assert_called_once()
    up_pos.assert_not_called()
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_warm_empty_redis_still_success() -> None:
    db = MagicMock()
    with (
        patch.object(m, "_redis_client", return_value=None),
        patch.object(m, "_list_config_keys", return_value=["AshareShortBreakoutStrategy:5:10"]),
        patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta") as save,
    ):
        out = m.warm_watchlist_strategy_cache(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert out["written_signals"] == 0
    assert "桥接" in out["message"] or "Redis" in out["message"]
    assert save.call_args.kwargs["last_success"] is True
```

- [ ] **Step 2: 跑测确认失败（旧 skipped 行为）**

```bash
cd backend && uv run pytest tests/test_ops_warm_watchlist_strategy.py -q
```

Expected: FAIL（旧实现恒 skipped 或缺 helper）

- [ ] **Step 3: 实现**

```python
# backend/app/services/ops_warm_watchlist_strategy.py
"""自选策略 cache 预热：Redis → PG 桥（不跑策略引擎）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.redis_keys import KEY_PREFIX
from app.services.ops_scheduler import save_job_run_meta
from app.services.quotes import get_quote_store
from app.services.strategy_board import DEFAULT_CONFIG_KEY, _parse_payload

JOB_ID = "warm_watchlist_strategy_cache"
_CHINA_TZ = timezone(timedelta(hours=8))


def _redis_client():
    store = get_quote_store()
    if not store.available():
        return None
    return store._client  # noqa: SLF001


def _today() -> str:
    return datetime.now(_CHINA_TZ).date().isoformat()


def _list_config_keys(db: Session) -> list[str]:
    keys = {DEFAULT_CONFIG_KEY}
    rows = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE namespace = 'watchlist' AND key = 'signal_config'
            """
        )
    ).scalars().all()
    for row in rows:
        if not isinstance(row, dict):
            continue
        cls = str(row.get("class_name") or "AshareShortBreakoutStrategy").strip()
        try:
            fast = max(2, min(int(row.get("fast_window") or 5), 60))
            slow = max(fast + 1, min(int(row.get("slow_window") or 10), 120))
        except (TypeError, ValueError):
            continue
        keys.add(f"{cls}:{fast}:{slow}")
    return sorted(keys)


def _upsert_signal(
    db: Session,
    *,
    vt_symbol: str,
    config_key: str,
    bar_as_of: str,
    payload: str,
    updated_at: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO cache.watchlist_signal_cache (
                vt_symbol, config_key, bar_as_of, payload, updated_at
            ) VALUES (
                :vt, :ck, :ba, :payload, :ua
            )
            ON CONFLICT (vt_symbol, config_key, bar_as_of) DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {"vt": vt_symbol, "ck": config_key, "ba": bar_as_of, "payload": payload, "ua": updated_at},
    )


def _upsert_position(
    db: Session,
    *,
    vt_symbol: str,
    config_key: str,
    bar_as_of: str,
    position_key: str,
    payload: str,
    updated_at: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO cache.watchlist_position_cache (
                vt_symbol, config_key, bar_as_of, position_key, payload, updated_at
            ) VALUES (
                :vt, :ck, :ba, :pk, :payload, :ua
            )
            ON CONFLICT (vt_symbol, config_key, bar_as_of, position_key) DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "vt": vt_symbol,
            "ck": config_key,
            "ba": bar_as_of,
            "pk": position_key,
            "payload": payload,
            "ua": updated_at,
        },
    )


def _bridge_config(db: Session, client: Any, config_key: str) -> tuple[int, int]:
    written_s = 0
    written_p = 0
    today = _today()
    sig_prefix = f"{KEY_PREFIX}:cache:signal:latest:{config_key}:"
    for key in client.scan_iter(match=f"{sig_prefix}*", count=100):
        text_key = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        vt = text_key[len(sig_prefix) :] if text_key.startswith(sig_prefix) else ""
        if not vt:
            continue
        raw = client.get(key)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if not isinstance(raw, str) or not raw.strip():
            continue
        snap = _parse_payload(raw)
        bar_as_of = today
        updated_at = today
        if isinstance(snap, dict):
            bar_as_of = str(snap.get("_bar_as_of") or snap.get("as_of") or today)[:32]
            updated_at = str(snap.get("_updated_at") or today)[:64]
            payload = json.dumps(
                {k: v for k, v in snap.items() if not str(k).startswith("_")},
                ensure_ascii=False,
            )
        else:
            payload = raw
        _upsert_signal(
            db,
            vt_symbol=vt,
            config_key=config_key,
            bar_as_of=bar_as_of or today,
            payload=payload,
            updated_at=updated_at or today,
        )
        written_s += 1

    pos_prefix = f"{KEY_PREFIX}:cache:position:latest:{config_key}:"
    for key in client.scan_iter(match=f"{pos_prefix}*", count=100):
        text_key = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        rest = text_key[len(pos_prefix) :] if text_key.startswith(pos_prefix) else ""
        # rest = "{vt}:{position_key}" — vt 含点号，position_key 为最后一段
        if ":" not in rest:
            continue
        vt, position_key = rest.rsplit(":", 1)
        if not vt or not position_key:
            continue
        raw = client.get(key)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if not isinstance(raw, str) or not raw.strip():
            continue
        snap = _parse_payload(raw)
        bar_as_of = today
        updated_at = today
        if isinstance(snap, dict):
            bar_as_of = str(snap.get("_bar_as_of") or snap.get("as_of") or today)[:32]
            updated_at = str(snap.get("_updated_at") or today)[:64]
            payload = json.dumps(
                {k: v for k, v in snap.items() if not str(k).startswith("_")},
                ensure_ascii=False,
            )
        else:
            payload = raw
        _upsert_position(
            db,
            vt_symbol=vt,
            config_key=config_key,
            bar_as_of=bar_as_of or today,
            position_key=position_key,
            payload=payload,
            updated_at=updated_at or today,
        )
        written_p += 1
    return written_s, written_p


def warm_watchlist_strategy_cache(db: Session) -> dict[str, Any]:
    config_keys = _list_config_keys(db)
    client = _redis_client()
    written_s = 0
    written_p = 0
    if client is not None:
        for ck in config_keys:
            s, p = _bridge_config(db, client, ck)
            written_s += s
            written_p += p
        db.commit()
    msg = f"策略 cache 桥接：signals={written_s} positions={written_p}"
    if client is None:
        msg = "无 Redis 信号可桥接（client 不可用）"
    elif written_s == 0 and written_p == 0:
        msg = "无 Redis 信号可桥接（0 命中）"
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": msg,
        "written_signals": written_s,
        "written_positions": written_p,
    }
```

同步改 catalog 本 job 描述为例如：`Redis signal/position → watchlist_*_cache（桥接，Web 可跑）`。

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_ops_warm_watchlist_strategy.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_warm_watchlist_strategy.py \
  backend/app/services/ops_catalog.py \
  backend/tests/test_ops_warm_watchlist_strategy.py
git commit -m "$(cat <<'EOF'
feat(ops): 做实 warm_watchlist_strategy_cache Redis→PG 桥

有信号则 upsert cache；无 Redis 仍 success 非 skipped。
EOF
)"
```

---

### Task 2: 做实 `prefetch_concept_board`

**Files:**
- Modify: `backend/app/services/ops_prefetch_concept_board.py`
- Modify: `backend/app/services/ops_catalog.py`（本 job 描述）
- Modify: `backend/tests/test_ops_prefetch_concept_board.py`

**Interfaces:**
- Produces: `prefetch_concept_board(db) -> {success, skipped, message, ...透传 days 可选}`
- Consumes: `ops_sync_sector.sync_sector_flow_daily`, `save_job_run_meta`

- [ ] **Step 1: 重写测试**

```python
# backend/tests/test_ops_prefetch_concept_board.py
from unittest.mock import MagicMock, patch

from app.services import ops_prefetch_concept_board as m


def test_concept_delegates_success() -> None:
    db = MagicMock()
    child = {"success": True, "skipped": False, "message": "ok 2 days", "days": 2}
    with (
        patch("app.services.ops_prefetch_concept_board.sync_sector_flow_daily", return_value=child),
        patch("app.services.ops_prefetch_concept_board.save_job_run_meta") as save,
    ):
        out = m.prefetch_concept_board(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert "概念预拉" in out["message"]
    assert "sector sync" in out["message"] or "ok" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_concept_delegates_skipped() -> None:
    db = MagicMock()
    child = {"success": False, "skipped": True, "message": "Tushare token missing", "days": 0}
    with (
        patch("app.services.ops_prefetch_concept_board.sync_sector_flow_daily", return_value=child),
        patch("app.services.ops_prefetch_concept_board.save_job_run_meta") as save,
    ):
        out = m.prefetch_concept_board(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "token" in out["message"].lower() or "Tushare" in out["message"]
    assert save.call_args.kwargs["last_success"] is False
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_prefetch_concept_board.py -q
```

Expected: FAIL

- [ ] **Step 3: 实现**

```python
# backend/app/services/ops_prefetch_concept_board.py
"""概念板块预拉：复用 sync_sector_flow_daily（含 ths/dc 概念资金）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta
from app.services.ops_sync_sector import sync_sector_flow_daily

JOB_ID = "prefetch_concept_board"


def prefetch_concept_board(db: Session) -> dict[str, Any]:
    child = sync_sector_flow_daily(db)
    skipped = bool(child.get("skipped"))
    success = bool(child.get("success"))
    child_msg = str(child.get("message") or "")
    if success and not skipped:
        message = f"概念预拉（复用 sector sync）：{child_msg}"
        last_success = True
    else:
        message = child_msg or "概念预拉失败"
        last_success = False
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=last_success)
    out: dict[str, Any] = {
        "success": success,
        "skipped": skipped,
        "message": message,
    }
    if "days" in child:
        out["days"] = child["days"]
    return out
```

catalog 描述改为：`复用 sync_sector_flow_daily 概念资金 → sector_flow_daily（Web 可跑）`。

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_ops_prefetch_concept_board.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_prefetch_concept_board.py \
  backend/app/services/ops_catalog.py \
  backend/tests/test_ops_prefetch_concept_board.py
git commit -m "$(cat <<'EOF'
feat(ops): 做实 prefetch_concept_board 复用 sector sync

有 token 时写入概念资金；无 token 透传 skipped。
EOF
)"
```

---

### Task 3: 做实 `fill_focus_pool_minute`

**Files:**
- Modify: `backend/app/services/ops_fill_focus_pool_minute.py`
- Modify: `backend/app/services/ops_catalog.py`（本 job 描述）
- Modify: `backend/tests/test_ops_fill_focus_pool_minute.py`

**Interfaces:**
- Produces: `fill_focus_pool_minute(db) -> {success, skipped: False, pool_size, with_daily, with_1m, missing_1m, message}`
- Consumes: `ops_bars_fill.list_watchlist_symbols`, `save_job_run_meta`

- [ ] **Step 1: 重写测试**

```python
# backend/tests/test_ops_fill_focus_pool_minute.py
from unittest.mock import MagicMock, patch

from app.services import ops_fill_focus_pool_minute as m


def test_minute_inventory_success() -> None:
    db = MagicMock()
    pool = [("600519", "SSE"), ("000001", "SZSE")]
    with (
        patch.object(m, "list_watchlist_symbols", return_value=pool),
        patch.object(m, "_count_overview", side_effect=[2, 0]),  # daily, 1m
        patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta") as save,
    ):
        out = m.fill_focus_pool_minute(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert out["pool_size"] == 2
    assert out["with_daily"] == 2
    assert out["with_1m"] == 0
    assert out["missing_1m"] == 2
    assert "1m 下载未接入" in out["message"]
    assert "盘点" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_minute_empty_pool_still_success() -> None:
    db = MagicMock()
    with (
        patch.object(m, "list_watchlist_symbols", return_value=[]),
        patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta") as save,
    ):
        out = m.fill_focus_pool_minute(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["pool_size"] == 0
    assert out["missing_1m"] == 0
    assert "1m 下载未接入" in out["message"]
    assert save.call_args.kwargs["last_success"] is True
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_fill_focus_pool_minute.py -q
```

Expected: FAIL

- [ ] **Step 3: 实现**

```python
# backend/app/services/ops_fill_focus_pool_minute.py
"""关注池 1m：薄盘点（不下载）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ops_bars_fill import list_watchlist_symbols
from app.services.ops_scheduler import save_job_run_meta
from app.services.symbols import normalize_exchange

JOB_ID = "fill_focus_pool_minute"
POOL_CAP = 500


def _count_overview(
    db: Session,
    pool: list[tuple[str, str]],
    *,
    interval: str,
) -> int:
    if not pool:
        return 0
    # (symbol, exchange) pairs
    syms = [s for s, _ in pool]
    exchs = [normalize_exchange(e) for _, e in pool]
    row = db.execute(
        text(
            """
            SELECT COUNT(*)::int AS n
            FROM public.dbbaroverview o
            WHERE o.interval = :iv
              AND EXISTS (
                SELECT 1
                FROM unnest(CAST(:syms AS text[]), CAST(:exchs AS text[])) AS p(symbol, exchange)
                WHERE p.symbol = o.symbol AND p.exchange = o.exchange
              )
            """
        ),
        {"iv": interval, "syms": syms, "exchs": exchs},
    ).mappings().first()
    return int((row or {}).get("n") or 0)


def fill_focus_pool_minute(db: Session) -> dict[str, Any]:
    raw = list_watchlist_symbols(db)
    truncated = len(raw) > POOL_CAP
    pool = raw[:POOL_CAP]
    pool_size = len(pool)
    with_daily = _count_overview(db, pool, interval="d") if pool_size else 0
    with_1m = _count_overview(db, pool, interval="1m") if pool_size else 0
    missing_1m = pool_size - with_1m
    msg = (
        f"1m 下载未接入，本跑仅盘点：pool={pool_size} daily={with_daily} "
        f"1m={with_1m} missing_1m={missing_1m}"
    )
    if truncated:
        msg += f"（已截断至 {POOL_CAP}）"
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "pool_size": pool_size,
        "with_daily": with_daily,
        "with_1m": with_1m,
        "missing_1m": missing_1m,
        "message": msg,
    }
```

若 `unnest` 双数组在测试/驱动上别扭，实现可改为循环 `get_overview_row` 风格计数（仍须盘点、不写 K）；测试已 mock `_count_overview`。

catalog 描述：`自选关注池 d/1m overview 盘点（1m 下载未接入，Web 可跑）`。

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_ops_fill_focus_pool_minute.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_fill_focus_pool_minute.py \
  backend/app/services/ops_catalog.py \
  backend/tests/test_ops_fill_focus_pool_minute.py
git commit -m "$(cat <<'EOF'
feat(ops): 做实 fill_focus_pool_minute 关注池盘点

统计自选 d/1m overview；不下载 1m，非 skipped。
EOF
)"
```

---

### Task 4: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

替换旧「恒 skipped」三条为：

```markdown
- [ ] Ops 手动跑 **`warm_watchlist_strategy_cache`** 非 skipped（Redis→PG 桥；无信号亦 success）；文案含桥接/Redis
- [ ] Ops 手动跑 **`prefetch_concept_board`**（复用 sector sync；有 token 非 skipped；无 token 可 skipped）；文案含「概念预拉」或 sector
- [ ] Ops 手动跑 **`fill_focus_pool_minute`** 非 skipped（盘点 pool/daily/1m）；文案含「1m 下载未接入」与「盘点」
```

- [ ] **Step 2: roadmap**

在 #26 后追加：

```markdown
27. ~~Ops 三 skipped job 薄做实~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-skipped-jobs-thin-design.md)）
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
docs: 记录 Ops 三 skipped job 薄做实完成

更新 smoke 与路线图 #27。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| §1 策略 Redis→PG | 1 |
| §2 概念委托 sector | 2 |
| §3 1m 盘点 | 3 |
| §4 catalog | 1–3 |
| §5 测试 | 1–3 |
| §6–7 文档 / check | 4 |
| 不引入队列 / 不真下 1m / 不跑策略 | Global + 各 Task |

无 TBD。predict/队列/ths_member/1m 下载明确不做。

---

# Ops skipped jobs thin SDD progress

- Task 1: complete — `40bca59` — Spec ✅ · Approved
- Task 2: complete — `c7cc0ae` — Spec ✅ · Approved
- Task 3: complete — `5d15bcb` — Spec ✅ · Approved
- Task 4: complete — `e55d150` — Spec ✅ · Approved
- Final: ready for finishing (local main)
