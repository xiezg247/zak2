# 策略信号日 K 双均线启发式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 日 K 双均线启发式写入 `watchlist_signal_cache`；升级 `warm_watchlist_strategy_cache`（先桥后算）。

**Architecture:** 纯函数模块 `strategy_signal_ma`；warm job 保留 Redis→PG，再对全站自选并集 × config_keys 真算 upsert；更新看盘 note。

**Tech Stack:** FastAPI、SQLAlchemy、pytest

**Spec:** `docs/superpowers/specs/2026-08-13-strategy-ma-signal-heuristic-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不写 position cache；不移植 ShortBreakout 全规则
- 缺 K 线 skip，不拖垮 job；空池仍 success
- 保留 Redis→PG 桥；真算覆盖同 config_key
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/strategy_signal_ma.py` | SMA + 金叉/死叉 payload |
| `backend/tests/test_strategy_signal_ma.py` | 算法单测 |
| `backend/app/services/ops_warm_watchlist_strategy.py` | 桥 + 真算 |
| `backend/tests/test_ops_warm_watchlist_strategy.py` | job 测 |
| `backend/app/services/ops_catalog.py` | 描述 |
| `backend/app/services/strategy_board.py` | 空 cache note |
| `backend/tests/test_strategy_board.py` | note 断言 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | #29 |

---

### Task 1: `strategy_signal_ma` 纯函数

**Files:**
- Create: `backend/app/services/strategy_signal_ma.py`
- Create: `backend/tests/test_strategy_signal_ma.py`

**Interfaces:**
- Produces: `parse_config_key(ck) -> tuple[int,int] | None`
- Produces: `compute_ma_signal(closes, *, volumes=None, fast, slow, vt_symbol, as_of) -> dict | None`
- Produces: `sma(values, window) -> list[float|None]`（可内部）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_strategy_signal_ma.py
from app.services import strategy_signal_ma as m


def test_parse_config_key() -> None:
    assert m.parse_config_key("AshareShortBreakoutStrategy:5:10") == (5, 10)
    assert m.parse_config_key("bad") is None
    assert m.parse_config_key("X:10:5") is None  # fast >= slow


def test_golden_cross_buy() -> None:
    # 构造：慢线更稳，后段快线上穿
    # 简单序列：前段下跌/走平后上涨，使 5/10 金叉出现在末尾
    closes = [10.0] * 10 + [9.0] * 5 + [11.0, 12.0, 13.0, 14.0, 15.0]
    out = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert out is not None
    assert out["signal"] in {"buy", "sell", "hold"}
    assert "启发式" in out["reason_summary"]
    assert out["vt_symbol"] == "600519.SSE"
    assert "ma_gap_pct" in out


def test_insufficient_returns_none() -> None:
    assert m.compute_ma_signal([1.0, 2.0], fast=5, slow=10, vt_symbol="x", as_of="2026-01-01") is None
```

补充：用可控序列分别断言 buy / sell / hold（可用手算短序列；或 mock `sma` 输出）。推荐显式：

```python
def test_signal_from_forced_ma(monkeypatch) -> None:
    # 长度 3：index 1 与 2 为有效交叉点
    closes = [1.0, 2.0, 3.0]
    monkeypatch.setattr(
        m,
        "sma",
        lambda values, w: (
            [None, 1.0, 3.0] if w == 2 else [None, 2.0, 2.0]
        ),
    )
    # 昨 fast1<=slow2 且今 fast3>slow2 → buy；此处 fast_window=2 slow=3 需匹配
    # 更简单：直接测 _cross_signal(prev_f, prev_s, f, s)
```

若实现暴露 `cross_kind(pf, ps, f, s) -> buy|sell|hold`，测该函数更稳：

```python
def test_cross_kind() -> None:
    assert m.cross_kind(1.0, 2.0, 3.0, 2.0) == "buy"
    assert m.cross_kind(3.0, 2.0, 1.0, 2.0) == "sell"
    assert m.cross_kind(2.0, 2.0, 2.1, 2.0) == "hold"
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_strategy_signal_ma.py -q
```

Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# backend/app/services/strategy_signal_ma.py
"""日 K 双均线启发式信号（非桌面 ShortBreakout）。"""

from __future__ import annotations

from typing import Any


def sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if window <= 0:
        return out
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out[i] = s / window
    return out


def parse_config_key(config_key: str) -> tuple[int, int] | None:
    parts = (config_key or "").strip().split(":")
    if len(parts) < 3:
        return None
    try:
        fast = int(parts[-2])
        slow = int(parts[-1])
    except ValueError:
        return None
    if fast < 2 or slow <= fast or slow > 120:
        return None
    return fast, slow


def cross_kind(pf: float, ps: float, f: float, s: float) -> str:
    if pf <= ps and f > s:
        return "buy"
    if pf >= ps and f < s:
        return "sell"
    return "hold"


_LABEL = {"buy": "买入", "sell": "卖出", "hold": "观望"}


def compute_ma_signal(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    fast: int,
    slow: int,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    if fast >= slow or len(closes) < slow + 1:
        return None
    fast_ma = sma(closes, fast)
    slow_ma = sma(closes, slow)
    i = len(closes) - 1
    j = i - 1
    f, s = fast_ma[i], slow_ma[i]
    pf, ps = fast_ma[j], slow_ma[j]
    if None in (f, s, pf, ps):
        return None
    kind = cross_kind(pf, ps, f, s)
    gap = (f - s) / s * 100.0 if s else 0.0
    vol_ratio = None
    if volumes and len(volumes) == len(closes) and len(volumes) >= 5:
        last = volumes[-1]
        avg5 = sum(volumes[-5:]) / 5.0
        if avg5 > 0:
            vol_ratio = last / avg5
    reason = f"{fast}/{slow} 日均线"
    if kind == "buy":
        reason += "金叉（启发式）"
    elif kind == "sell":
        reason += "死叉（启发式）"
    else:
        reason += "持有/观望（启发式）"
    out: dict[str, Any] = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": closes[-1],
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(abs(gap), 4),
    }
    if vol_ratio is not None:
        out["volume_ratio_5d"] = round(vol_ratio, 4)
    return out
```

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_strategy_signal_ma.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/strategy_signal_ma.py backend/tests/test_strategy_signal_ma.py
git commit -m "$(cat <<'EOF'
feat(strategy): 新增日 K 双均线启发式信号纯函数

金叉/死叉/hold；payload 对齐策略看盘字段。
EOF
)"
```

---

### Task 2: 升级 `warm_watchlist_strategy_cache`

**Files:**
- Modify: `backend/app/services/ops_warm_watchlist_strategy.py`
- Modify: `backend/app/services/ops_catalog.py`
- Modify: `backend/tests/test_ops_warm_watchlist_strategy.py`

**Interfaces:**
- Consumes: `strategy_signal_ma.parse_config_key` / `compute_ma_signal`
- Consumes: `ops_bars_fill.list_watchlist_symbols`；日 K 可选加载（勿因 404 失败）
- Produces: 返回增加 `computed`, `skipped_bars`；message 含「双均线启发式」

- [ ] **Step 1: 扩展测试**

保留原桥接测；新增：

```python
def test_warm_computes_ma_signals() -> None:
    db = MagicMock()
    with (
        patch.object(m, "_redis_client", return_value=None),
        patch.object(m, "_list_config_keys", return_value=["AshareShortBreakoutStrategy:5:10"]),
        patch.object(m, "list_watchlist_symbols", return_value=[("600519", "SSE")]),
        patch.object(
            m,
            "_load_daily_closes",
            return_value=([10.0] * 20, [100.0] * 20, "2026-08-13"),
        ),
        patch.object(
            m,
            "compute_ma_signal",
            return_value={
                "signal": "hold",
                "signal_label": "观望",
                "vt_symbol": "600519.SSE",
                "as_of": "2026-08-13",
                "signal_date": "2026-08-13",
                "last_close": 10.0,
                "ma_gap_pct": 0.1,
                "reason_summary": "5/10 日均线持有/观望（启发式）",
                "strength": 0.1,
            },
        ) as comp,
        patch.object(m, "_upsert_signal") as up,
        patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta") as save,
    ):
        out = m.warm_watchlist_strategy_cache(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert out["computed"] == 1
    assert "双均线启发式" in out["message"]
    comp.assert_called()
    up.assert_called()
    assert save.call_args.kwargs["last_success"] is True


def test_warm_skips_missing_bars() -> None:
    db = MagicMock()
    with (
        patch.object(m, "_redis_client", return_value=None),
        patch.object(m, "_list_config_keys", return_value=["AshareShortBreakoutStrategy:5:10"]),
        patch.object(m, "list_watchlist_symbols", return_value=[("600519", "SSE")]),
        patch.object(m, "_load_daily_closes", return_value=None),
        patch.object(m, "_upsert_signal") as up,
        patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta"),
    ):
        out = m.warm_watchlist_strategy_cache(db)
    assert out["computed"] == 0
    assert out["skipped_bars"] >= 1
    up.assert_not_called()
```

更新 `test_warm_empty_redis_still_success`：允许 message 含启发式（桥 0 + 算 0）。

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_warm_watchlist_strategy.py -q
```

Expected: FAIL（缺 computed 等）

- [ ] **Step 3: 实现加载 + job 扩展**

```python
# ops_warm_watchlist_strategy.py 增补
import json
from app.services.ops_bars_fill import list_watchlist_symbols
from app.services.strategy_signal_ma import compute_ma_signal, parse_config_key
from app.services.symbols import to_vt_symbol
from app.models.bars import DbBarData
from sqlalchemy import select

POOL_CAP = 500


def _load_daily_closes(
    db: Session, *, symbol: str, exchange: str, limit: int
) -> tuple[list[float], list[float], str] | None:
    """返回 (closes, volumes, as_of)；无数据返回 None（不抛）。"""
    from app.services.symbols import normalize_exchange

    exch = normalize_exchange(exchange)
    rows = list(
        db.scalars(
            select(DbBarData)
            .where(
                DbBarData.symbol == symbol,
                DbBarData.exchange == exch,
                DbBarData.interval == "d",
            )
            .order_by(DbBarData.datetime.desc())
            .limit(limit)
        )
    )
    if not rows:
        return None
    rows.reverse()
    closes = [float(r.close_price or 0) for r in rows]
    volumes = [float(r.volume or 0) for r in rows]
    as_of = rows[-1].datetime.date().isoformat()
    return closes, volumes, as_of


def _compute_pool(db: Session, config_keys: list[str]) -> tuple[int, int]:
    pool = list_watchlist_symbols(db)[:POOL_CAP]
    computed = 0
    skipped_bars = 0
    today = _today()
    for ck in config_keys:
        parsed = parse_config_key(ck)
        if not parsed:
            continue
        fast, slow = parsed
        limit = min(200, max(slow * 3, 60))
        for symbol, exchange in pool:
            loaded = _load_daily_closes(db, symbol=symbol, exchange=exchange, limit=limit)
            if not loaded:
                skipped_bars += 1
                continue
            closes, volumes, as_of = loaded
            vt = to_vt_symbol(symbol, exchange)
            snap = compute_ma_signal(
                closes,
                volumes=volumes,
                fast=fast,
                slow=slow,
                vt_symbol=vt,
                as_of=as_of,
            )
            if not snap:
                skipped_bars += 1
                continue
            _upsert_signal(
                db,
                vt_symbol=vt,
                config_key=ck,
                bar_as_of=as_of,
                payload=json.dumps(snap, ensure_ascii=False),
                updated_at=today,
            )
            computed += 1
    return computed, skipped_bars


def warm_watchlist_strategy_cache(db: Session) -> dict[str, Any]:
    config_keys = _list_config_keys(db)
    # ... existing bridge ...
    computed, skipped_bars = _compute_pool(db, config_keys)
    db.commit()
    msg = (
        f"策略 cache：桥接 signals={written_s} positions={written_p}；"
        f"双均线启发式 computed={computed} skipped_bars={skipped_bars}"
    )
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": msg,
        "written_signals": written_s,
        "written_positions": written_p,
        "computed": computed,
        "skipped_bars": skipped_bars,
    }
```

catalog 描述：`Redis 桥 + 日 K 双均线启发式 → watchlist_signal_cache（Web 可跑）`。

注意：桥接段已有 `db.commit()` 时可保留；真算后再 commit 一次即可。

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_ops_warm_watchlist_strategy.py tests/test_strategy_signal_ma.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_warm_watchlist_strategy.py \
  backend/app/services/ops_catalog.py \
  backend/tests/test_ops_warm_watchlist_strategy.py
git commit -m "$(cat <<'EOF'
feat(ops): warm_watchlist_strategy_cache 增加双均线真算

先 Redis 桥再日 K 启发式写 signal cache。
EOF
)"
```

---

### Task 3: 看盘 note

**Files:**
- Modify: `backend/app/services/strategy_board.py`
- Modify: `backend/tests/test_strategy_board.py`（若已有 note 测则改断言）

**Interfaces:**
- 空 signals note 引导 Ops `warm_watchlist_strategy_cache`（双均线启发式）

- [ ] **Step 1: 更新/补充测试**

```python
def test_note_empty_mentions_heuristic_job() -> None:
    # 按现有 test_strategy_board 风格 mock 到 signals/positions 皆空
    # assert "warm_watchlist_strategy_cache" in note or "双均线" in note
    # assert "尚未接入策略引擎预热" not in note
```

现有 `test_load_strategy_board_*` 断言含「尚未接入策略引擎」——必须改为启发式/job 引导，且仍断言无「桌面」。

- [ ] **Step 2: 改 note 文案**

```python
elif not signals and not positions:
    note = (
        "暂无策略缓存。可 Ops 跑 warm_watchlist_strategy_cache（日 K 双均线启发式），"
        "或确认 Redis/PG 已有信号缓存；亦可先维护信号名单与持仓记账。"
    )
elif panel_symbols and not signals:
    note = (
        f"信号名单 {len(panel_symbols)} 只，暂无策略 cache"
        "（可编辑名单，或 Ops 跑 warm_watchlist_strategy_cache / 确认 cache）。"
    )
elif not signals:
    note = (
        "持仓来自记账表；信号 cache 为空"
        "（可 Ops 跑 warm_watchlist_strategy_cache，或确认 cache 已写入）。"
    )
```

- [ ] **Step 3: pytest**

```bash
cd backend && uv run pytest tests/test_strategy_board.py -q
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/strategy_board.py backend/tests/test_strategy_board.py
git commit -m "$(cat <<'EOF'
fix(watchlist): 策略看盘空态引导双均线启发式预热

去掉「尚未接入策略引擎预热」过时文案。
EOF
)"
```

---

### Task 4: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

替换 warm 条：

```markdown
- [ ] Ops 手动跑 **`warm_watchlist_strategy_cache`** 非 skipped（Redis 桥 + 日 K 双均线启发式）；有日 K 的自选在 `/watchlist` 策略看盘可见信号；文案含「双均线启发式」
```

- [ ] **Step 2: roadmap**

```markdown
29. ~~策略信号日 K 双均线启发式~~（已完成 → [spec](./superpowers/specs/2026-08-13-strategy-ma-signal-heuristic-design.md)）
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
docs: 记录策略信号日 K 双均线启发式完成

更新 smoke 与路线图 #29。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| §1 MA 模块 | 1 |
| §2 warm job | 2 |
| §3 note | 3 |
| §4 测试 | 1–3 |
| §5–6 文档 | 4 |
| 不写 position / 保留桥 | Global + Task 2 |

无 TBD。日 K 加载必须不抛 404。
