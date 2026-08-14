# 策略双均线信号加深（v2）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 双均线交叉确认 N=2 + 强度档写入 payload，透出到策略看盘强度列。

**Architecture:** 扩展 `strategy_signal_ma.compute_ma_signal`（交叉当日 hold，昨交叉+今同向才 buy/sell；写 `strength_tier`）；`strategy_board._pack_signal_row` 透出；看盘强度列「档 · 数值」；catalog/warm message 标 v2。

**Tech Stack:** FastAPI · Vue 3 · pytest

**Spec:** `docs/superpowers/specs/2026-08-14-strategy-ma-signal-v2-design.md`

## Global Constraints

- 确认 N=2 写死；分档阈值 `<0.3` 弱 · `[0.3,1.0)` 中 · `≥1.0` 强
- 扩展现有模块，不新建 `*_v2` 文件
- 不改回测引擎；量比不改档；无可调 UI
- 数据不足 `slow+2` → `None`
- Commit 简体中文；不 push

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/strategy_signal_ma.py` | 确认 + 分档 |
| `backend/tests/test_strategy_signal_ma.py` | 算法单测（改写旧金叉当日测） |
| `backend/app/schemas/watchlist.py` | `StrategySignalRow` 增字段 |
| `backend/app/services/strategy_board.py` | `_pack_signal_row` 透出 |
| `backend/tests/test_strategy_board.py` | 透出断言（可扩一条） |
| `backend/app/services/ops_catalog.py` | 描述含确认 N=2 / v2 |
| `backend/app/services/ops_warm_watchlist_strategy.py` | message 含 v2 |
| `backend/tests/test_ops_warm_watchlist_strategy.py` | message 断言 |
| `frontend/src/api/watchlist.ts` | 类型 |
| `frontend/src/views/WatchlistView.vue` | 强度列展示 |
| docs | roadmap #46 + smoke |

---

### Task 1: `compute_ma_signal` 确认 + 分档

**Files:**
- Modify: `backend/app/services/strategy_signal_ma.py`
- Modify: `backend/tests/test_strategy_signal_ma.py`

**Interfaces:**
- Consumes: 现有 `sma` / `cross_kind` / `compute_ma_signal(...)`
- Produces: payload 含 `confirm_bars=2`、`strength_tier`、`strength_tier_label`；确认语义见 spec §1.1
- Produces（可选 helper）: `strength_tier_for(gap_abs: float) -> tuple[str, str]`

- [ ] **Step 1: 改写/新增失败测**

替换/扩充 `backend/tests/test_strategy_signal_ma.py`（保留 `parse_config_key` / `cross_kind`）：

```python
from __future__ import annotations

from app.services import strategy_signal_ma as m


def test_parse_config_key() -> None:
    assert m.parse_config_key("AshareShortBreakoutStrategy:5:10") == (5, 10)
    assert m.parse_config_key("bad") is None
    assert m.parse_config_key("X:10:5") is None


def test_cross_kind() -> None:
    assert m.cross_kind(1.0, 2.0, 3.0, 2.0) == "buy"
    assert m.cross_kind(3.0, 2.0, 1.0, 2.0) == "sell"
    assert m.cross_kind(2.0, 2.0, 2.1, 2.0) == "buy"


def test_strength_tier_boundaries() -> None:
    assert m.strength_tier_for(0.29) == ("weak", "弱")
    assert m.strength_tier_for(0.3) == ("mid", "中")
    assert m.strength_tier_for(0.99) == ("mid", "中")
    assert m.strength_tier_for(1.0) == ("strong", "强")


def test_same_day_cross_is_pending_hold(monkeypatch) -> None:
    """交叉发生在 j→i（当日）→ hold 待确认。"""
    closes = [1.0] * 12  # 长度足够；MA 由 mock 控制

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        n = len(values)
        # 仅末三根有值：k=n-3, j=n-2, i=n-1
        out: list[float | None] = [None] * n
        if window == 5:
            # k: fast<=slow, j: fast<=slow, i: fast>slow → 当日金叉
            out[-3], out[-2], out[-1] = 1.0, 1.0, 3.0
        else:  # slow=10
            out[-3], out[-2], out[-1] = 2.0, 2.0, 2.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    out = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert out is not None
    assert out["signal"] == "hold"
    assert "待确认" in out["reason_summary"]
    assert out["confirm_bars"] == 2
    assert out["strength_tier"] in {"weak", "mid", "strong"}
    assert out["strength_tier_label"] in {"弱", "中", "强"}


def test_confirmed_buy_after_cross(monkeypatch) -> None:
    """昨 k→j 金叉，今仍 fast>slow → buy 已确认。"""
    closes = [1.0] * 12

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        n = len(values)
        out: list[float | None] = [None] * n
        if window == 5:
            # k:1<=2, j:3>2 金叉；i:3.5>2 仍上方
            out[-3], out[-2], out[-1] = 1.0, 3.0, 3.5
        else:
            out[-3], out[-2], out[-1] = 2.0, 2.0, 2.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    out = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert out is not None
    assert out["signal"] == "buy"
    assert "已确认" in out["reason_summary"]
    assert "金叉" in out["reason_summary"]
    assert out["confirm_bars"] == 2


def test_confirmed_sell_after_cross(monkeypatch) -> None:
    closes = [1.0] * 12

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        n = len(values)
        out: list[float | None] = [None] * n
        if window == 5:
            out[-3], out[-2], out[-1] = 3.0, 1.0, 0.5
        else:
            out[-3], out[-2], out[-1] = 2.0, 2.0, 2.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    out = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert out is not None
    assert out["signal"] == "sell"
    assert "已确认" in out["reason_summary"]


def test_insufficient_slow_plus_two_returns_none() -> None:
    # slow=10 → 需至少 12 根
    assert (
        m.compute_ma_signal([1.0] * 11, fast=5, slow=10, vt_symbol="x", as_of="2026-01-01")
        is None
    )
```

删除或改写旧的 `test_golden_cross_buy`（深度 1 当日金叉断言 buy）——与 v2 冲突。

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_strategy_signal_ma.py -q
```

Expected: FAIL（缺 `strength_tier_for` / 仍当日 buy / 无待确认）

- [ ] **Step 3: 最小实现**

在 `strategy_signal_ma.py`：

```python
CONFIRM_BARS = 2

def strength_tier_for(gap_abs: float) -> tuple[str, str]:
    if gap_abs < 0.3:
        return "weak", "弱"
    if gap_abs < 1.0:
        return "mid", "中"
    return "strong", "强"
```

`compute_ma_signal` 核心逻辑：

```python
    if fast >= slow or len(closes) < slow + CONFIRM_BARS:
        return None
    fast_ma = sma(closes, fast)
    slow_ma = sma(closes, slow)
    i = len(closes) - 1
    j = i - 1
    k = i - 2
    f, s = fast_ma[i], slow_ma[i]
    pf, ps = fast_ma[j], slow_ma[j]
    kf, ks = fast_ma[k], slow_ma[k]
    if None in (f, s, pf, ps, kf, ks):
        return None

    same_day = cross_kind(pf, ps, f, s)
    prev_cross = cross_kind(kf, ks, pf, ps)

    if same_day in {"buy", "sell"}:
        kind = "hold"
        pending = True
        pending_kind = same_day
    elif prev_cross == "buy" and f > s:
        kind = "buy"
        pending = False
        pending_kind = "buy"
    elif prev_cross == "sell" and f < s:
        kind = "sell"
        pending = False
        pending_kind = "sell"
    else:
        kind = "hold"
        pending = False
        pending_kind = "hold"

    gap = (f - s) / s * 100.0 if s else 0.0
    gap_abs = abs(gap)
    tier, tier_label = strength_tier_for(gap_abs)

    # volume_ratio_5d 保持原逻辑
    reason = f"{fast}/{slow} 日均线"
    if pending and pending_kind == "buy":
        reason += f"金叉待确认（启发式·{tier_label}）"
    elif pending and pending_kind == "sell":
        reason += f"死叉待确认（启发式·{tier_label}）"
    elif kind == "buy":
        reason += f"金叉已确认（启发式·{tier_label}）"
    elif kind == "sell":
        reason += f"死叉已确认（启发式·{tier_label}）"
    else:
        reason += f"持有/观望（启发式·{tier_label}）"

    out = {
        "signal": kind,
        "signal_label": _LABEL[kind],
        "vt_symbol": vt_symbol,
        "as_of": as_of[:10],
        "signal_date": as_of[:10],
        "last_close": closes[-1],
        "ma_gap_pct": round(gap, 4),
        "reason_summary": reason,
        "strength": round(gap_abs, 4),
        "confirm_bars": CONFIRM_BARS,
        "strength_tier": tier,
        "strength_tier_label": tier_label,
    }
    # … volume_ratio_5d …
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
feat(strategy): 双均线信号确认 N=2 与强度档

交叉当日待确认；次日同向发信；payload 写档位。
EOF
)"
```

---

### Task 2: Board 透出 + 看盘强度列

**Files:**
- Modify: `backend/app/schemas/watchlist.py`（`StrategySignalRow`）
- Modify: `backend/app/services/strategy_board.py`（`_pack_signal_row`）
- Modify: `backend/tests/test_strategy_board.py`（或新建小测）
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`

**Interfaces:**
- Consumes: payload `strength_tier` / `strength_tier_label`
- Produces: `StrategySignalRow.strength_tier: str | None = None`、`strength_tier_label: str | None = None`

- [ ] **Step 1: 后端 schema + pack + 测**

`StrategySignalRow` 增加：

```python
    strength_tier: str | None = None
    strength_tier_label: str | None = None
```

`_pack_signal_row` 增加：

```python
        "strength_tier": str(snap.get("strength_tier") or "") or None,
        "strength_tier_label": str(snap.get("strength_tier_label") or "") or None,
```

在 `test_strategy_board.py` 增加（或独立函数测 `_pack_signal_row`）：

```python
def test_pack_signal_row_includes_tier() -> None:
    from app.services.strategy_board import _pack_signal_row

    row = _pack_signal_row(
        "600519.SSE",
        {
            "signal": "buy",
            "signal_label": "买入",
            "strength": 0.8,
            "strength_tier": "mid",
            "strength_tier_label": "中",
            "reason_summary": "金叉已确认",
        },
    )
    assert row["strength_tier"] == "mid"
    assert row["strength_tier_label"] == "中"
```

```bash
cd backend && uv run pytest tests/test_strategy_board.py::test_pack_signal_row_includes_tier -q
```

Expected: PASS（先写测再改 pack）

- [ ] **Step 2: 前端类型 + UI**

`watchlist.ts` `StrategySignalRow`：

```ts
  strength_tier?: string | null
  strength_tier_label?: string | null
```

`WatchlistView.vue` 强度单元格：

```html
<td>
  <template v-if="row.strength_tier_label">
    {{ row.strength_tier_label }}<span v-if="row.strength != null"> · {{ row.strength.toFixed(1) }}</span>
  </template>
  <template v-else>
    {{ row.strength != null ? row.strength.toFixed(0) : '—' }}
  </template>
</td>
```

- [ ] **Step 3: 构建**

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/watchlist.py backend/app/services/strategy_board.py \
  backend/tests/test_strategy_board.py frontend/src/api/watchlist.ts \
  frontend/src/views/WatchlistView.vue
git commit -m "$(cat <<'EOF'
feat(watchlist): 策略看盘强度列展示档位

透出 strength_tier；无档时回退数值。
EOF
)"
```

---

### Task 3: Catalog / warm 文案

**Files:**
- Modify: `backend/app/services/ops_catalog.py`
- Modify: `backend/app/services/ops_warm_watchlist_strategy.py`
- Modify: `backend/tests/test_ops_warm_watchlist_strategy.py`

**Interfaces:**
- message / catalog 须含「确认 N=2」或「双均线启发式 v2」（测试断言其一即可；推荐两者都写进 message：`双均线启发式 v2（确认 N=2）`）

- [ ] **Step 1: 改测断言**

将现有 `assert "双均线启发式" in out["message"]` 改为：

```python
    assert "双均线启发式 v2" in out["message"] or "确认 N=2" in out["message"]
```

并加 catalog 测：

```python
# backend/tests/test_ops_catalog.py
def test_warm_strategy_catalog_mentions_v2() -> None:
    from app.services.ops_catalog import JOB_SPECS

    spec = next(s for s in JOB_SPECS if s.job_id == "warm_watchlist_strategy_cache")
    assert "确认 N=2" in spec.description or "v2" in spec.description
```

- [ ] **Step 2: 实现文案**

`ops_warm_watchlist_strategy.py` message 示例：

```python
    msg = (
        f"双均线启发式 v2（确认 N=2） computed={computed} skipped_bars={skipped_bars}"
    )
```

`ops_catalog.py` 描述改为：

```text
Redis 桥 + 日 K 双均线启发式 v2（确认 N=2）→ watchlist_signal_cache（Web 可跑）
```

- [ ] **Step 3: 跑测**

```bash
cd backend && uv run pytest tests/test_ops_warm_watchlist_strategy.py tests/test_ops_catalog.py -q
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ops_catalog.py \
  backend/app/services/ops_warm_watchlist_strategy.py \
  backend/tests/test_ops_warm_watchlist_strategy.py \
  backend/tests/test_ops_catalog.py
git commit -m "$(cat <<'EOF'
docs(ops): 策略预热文案标明双均线启发式 v2

catalog 与 job message 含确认 N=2。
EOF
)"
```

（若未改 catalog 测文件则从 `git add` 去掉。）

---

### Task 4: 文档 + check.sh

**Files:**
- Modify: `docs/product-roadmap.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: roadmap #46**

```markdown
46. ~~策略双均线信号加深（确认 N=2 + 强度档）~~（已完成 → [spec](./superpowers/specs/2026-08-14-strategy-ma-signal-v2-design.md)）
```

- [ ] **Step 2: smoke**

在自选/策略相关条目附近：

```markdown
- [ ] Ops 跑 `warm_watchlist_strategy_cache` 后 message 含 v2/确认 N=2；`/watchlist` 策略看盘强度列可见「弱/中/强」档（或摘要含已确认/待确认）
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: OK

- [ ] **Step 4: Commit**

```bash
git add docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录策略双均线信号加深完成

路线图 #46 与 smoke 补确认/档位验收。
EOF
)"
```

---

## Spec coverage (self-review)

| Spec | Task |
|------|------|
| §1 确认 N=2 + 分档 | 1 |
| §2 Job/Schema 透出 | 2 + 3 |
| §3 看盘强度列 | 2 |
| §4 测试文档 | 1–4 |

无 TBD；旧当日金叉 buy 测在 Task 1 显式替换。
