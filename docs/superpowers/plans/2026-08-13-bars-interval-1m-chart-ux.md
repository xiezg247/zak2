# 日K / 1分 K 线切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自选与市场详情可在日K / 1分间切换出图；无 1m 时空态链 Ops；404 文案按周期区分。

**Architecture:** 改 `load_bars` 404 detail；`CandleChart` 增加 `interval` prop；`WatchlistView` / `MarketView` 就地加周期与 limit 芯片并调用已有 `watchlistApi.bars(vt, interval, limit)`。

**Tech Stack:** FastAPI · Vue 3 · pytest · vue-tsc

**Spec:** `docs/superpowers/specs/2026-08-13-bars-interval-1m-chart-ux-design.md`

## Global Constraints

- UI 周期仅 `d` | `1m`
- 日 limit：60/90/120，默认 90；1 分：240/480/1200，默认 480
- 不下载、不推送、不持久化偏好、不抽大面板
- 切标的保留当前周期与对应 limit
- Commit 简体中文；不 push

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/bars.py` | 404 文案按 interval |
| `backend/tests/test_zak_copy_closeout.py` 或新建 `test_bars_load.py` | 404 单测 |
| `frontend/src/components/CandleChart.vue` | `interval` 轴/hint |
| `frontend/src/views/WatchlistView.vue` | 周期+limit+空态 |
| `frontend/src/views/MarketView.vue` | 同上（无 OHLC 表） |
| `docs/product-roadmap.md` / `docs/smoke-checklist.md` | #45 + smoke |

---

### Task 1: load_bars 404 按周期

**Files:**
- Modify: `backend/app/services/bars.py`
- Modify: `backend/tests/test_zak_copy_closeout.py`（扩展现有空测）或 Create: `backend/tests/test_bars_load.py`

**Interfaces:**
- Consumes: `load_bars(db, *, symbol, exchange, interval="d", limit=120, end=None)`
- Produces: 无行时 404 detail 随 `interval` 变化（见下）

- [ ] **Step 1: 写失败测**

在 `backend/tests/test_bars_load.py`（推荐独立文件，避免搅乱 closeout）：

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import bars


def test_load_bars_empty_daily_ops_copy() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    with pytest.raises(HTTPException) as ei:
        bars.load_bars(db, symbol="600519", exchange="SHSE", interval="d")
    assert ei.value.status_code == 404
    assert "Ops" in ei.value.detail
    assert "日 K" in ei.value.detail or "全日 K" in ei.value.detail
    assert "fill_focus_pool_minute" not in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak"):
        assert bad not in ei.value.detail


def test_load_bars_empty_1m_points_to_focus_job() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    with pytest.raises(HTTPException) as ei:
        bars.load_bars(db, symbol="600519", exchange="SHSE", interval="1m")
    assert ei.value.status_code == 404
    assert "1 分" in ei.value.detail or "1分" in ei.value.detail
    assert "fill_focus_pool_minute" in ei.value.detail
    assert "Ops" in ei.value.detail
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_bars_load.py -q
```

Expected: FAIL（1m 文案仍含「补全日 K」或无 `fill_focus_pool_minute`）

- [ ] **Step 3: 最小实现**

改 `bars.py` 无行分支：

```python
    if not rows:
        if interval == "1m":
            detail = "无 1 分 K 线，请先在 Ops 运行 fill_focus_pool_minute"
        elif interval == "d":
            detail = "无 K 线数据，请先在 Ops 补全日 K"
        else:
            detail = "无 K 线数据"
        raise HTTPException(status_code=404, detail=detail)
```

（保留文件其余逻辑不变；`interval` 已在上方 normalize。）

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_bars_load.py tests/test_zak_copy_closeout.py::test_load_bars_empty_points_to_ops -q
```

Expected: PASS（既有日 K 空测仍过）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bars.py backend/tests/test_bars_load.py
git commit -m "$(cat <<'EOF'
fix(bars): 无数据 404 文案按周期区分

1m 指向 fill_focus_pool_minute，避免误导补全日 K。
EOF
)"
```

---

### Task 2: CandleChart interval 轴标签

**Files:**
- Modify: `frontend/src/components/CandleChart.vue`

**Interfaces:**
- Produces: prop `interval?: 'd' | '1m'`（默认 `'d'`）
- x 轴：`d` → `datetime.slice(5, 10)`；`1m` → 取 `HH:MM`（从 ISO/空格分隔串解析时分）
- hint：`d` → `slice(0, 10)`；`1m` → `MM-DD HH:MM`

- [ ] **Step 1: 扩展 props 与标签逻辑**

```ts
const props = withDefaults(
  defineProps<{
    bars: CandleBar[]
    width?: number
    height?: number
    interval?: 'd' | '1m'
  }>(),
  { width: 640, height: 280, interval: 'd' },
)

function axisLabel(dt: string): string {
  if (props.interval === '1m') {
    // "2026-08-13 09:31:00" 或 ISO → HH:MM
    const m = dt.match(/(\d{2}):(\d{2})/)
    return m ? `${m[1]}:${m[2]}` : dt.slice(11, 16)
  }
  return dt.slice(5, 10)
}

function hintTime(dt: string): string {
  if (props.interval === '1m') {
    const date = dt.slice(5, 10)
    const m = dt.match(/(\d{2}):(\d{2})/)
    return m ? `${date} ${m[1]}:${m[2]}` : dt.slice(0, 16)
  }
  return dt.slice(0, 10)
}
```

在 `layout` labels 循环里用 `axisLabel(data[i].datetime)`；模板 hint 用 `hintTime(last.datetime)`。

- [ ] **Step 2: 类型检查（本组件无单测）**

```bash
cd frontend && npm run build
```

Expected: 通过（或至少本文件无 tsc 错；若整仓其它错先记下，Task 3 一并绿）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CandleChart.vue
git commit -m "$(cat <<'EOF'
feat(ui): CandleChart 支持 1 分时分轴标签

日 K 保持 MM-DD；1 分显示 HH:MM。
EOF
)"
```

---

### Task 3: WatchlistView + MarketView 周期切换

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/MarketView.vue`

**Interfaces:**
- Consumes: `watchlistApi.bars(vt, interval, limit)`；`CandleChart` 的 `interval` prop
- 状态：`barInterval: 'd' | '1m'`；`barLimitDaily` / `barLimit1m`（或切换时写入当前 `barLimit`）

- [ ] **Step 1: WatchlistView 状态与 loadBars**

在 script 中（靠近现有 `barLimit`）：

```ts
const barInterval = ref<'d' | '1m'>('d')
const barLimitDaily = ref(90)
const barLimit1m = ref(480)

const barLimit = computed({
  get: () => (barInterval.value === '1m' ? barLimit1m.value : barLimitDaily.value),
  set: (n: number) => {
    if (barInterval.value === '1m') barLimit1m.value = n
    else barLimitDaily.value = n
  },
})

const barLimitChoices = computed(() =>
  barInterval.value === '1m' ? [240, 480, 1200] : [60, 90, 120],
)

async function loadBars() {
  barsError.value = ''
  bars.value = []
  if (!selected.value) {
    barsLoading.value = false
    return
  }
  barsLoading.value = true
  try {
    const resp = await watchlistApi.bars(
      selected.value.vt_symbol,
      barInterval.value,
      barLimit.value,
    )
    bars.value = resp.bars
  } catch (e) {
    barsError.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    barsLoading.value = false
  }
}
```

- `watch(barLimit, ...)` 改为同时 `watch([barLimit, barInterval], () => void loadBars())`（或分别 watch）。
- 切标的已有 `watch(selected, loadBars)`：保留周期，不重置 `barInterval`。

模板图区头部（示意）：

```html
<div class="limits">
  <button type="button" class="chip" :class="{ on: barInterval === 'd' }" @click="barInterval = 'd'">日K</button>
  <button type="button" class="chip" :class="{ on: barInterval === '1m' }" @click="barInterval = '1m'">1分</button>
</div>
<div class="limits">
  <button
    v-for="n in barLimitChoices"
    :key="n"
    type="button"
    class="chip"
    :class="{ on: barLimit === n }"
    @click="barLimit = n"
  >
    {{ barInterval === '1m' ? `${n}根` : `${n}日` }}
  </button>
</div>
```

文案：

- 加载：`barInterval === '1m' ? '加载 1 分 K…' : '加载日 K…'`
- 空/错 Ops：`barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'`
- meta：`…根 1 分 K` / `…根日 K`
- `<CandleChart :bars="bars" :interval="barInterval" />`
- OHLC 表日期列：展示完整 `datetime` 前 16 字符（含时分）即可；日 K 仍可读

- [ ] **Step 2: MarketView 同样逻辑**

`MarketView` 当前写死 `bars(..., 'd', 90)`：

- 增加相同 `barInterval` / `barLimitDaily` / `barLimit1m` / choices
- `loadBars` 传 interval+limit；watch 周期与 limit
- 详情区加周期+limit 芯片；加载/空态文案与 Ops 链同上
- `<CandleChart :bars="bars" :height="240" :interval="barInterval" />`
- 不加 OHLC 表

- [ ] **Step 3: 构建**

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/WatchlistView.vue frontend/src/views/MarketView.vue
git commit -m "$(cat <<'EOF'
feat(ui): 自选与市场详情支持日K/1分切换

limit 芯片随周期变化；空态分别引导 Ops。
EOF
)"
```

---

### Task 4: 文档 + check.sh

**Files:**
- Modify: `docs/product-roadmap.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: roadmap #45**

在近期待办末尾（#44 后）追加：

```markdown
45. ~~日K / 1分 K 线切换~~（已完成 → [spec](./superpowers/specs/2026-08-13-bars-interval-1m-chart-ux-design.md)）
```

- [ ] **Step 2: smoke**

在 §3 自选与 §5 市场各补一条，例如：

```markdown
- [ ] `/watchlist` 详情可切 **日K / 1分**；limit 芯片随周期变；无 1 分数据见「去 Ops 补全 1 分 K」；有数据出图且轴为时分
- [ ] `/market` 详情可切 **日K / 1分**；无 1 分数据见 Ops 链；有数据出图
```

（可紧挨现有日 K 空态条目。）

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: OK（pytest + frontend build）

- [ ] **Step 4: Commit**

```bash
git add docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录日K与1分K线切换完成

路线图 #45 与 smoke 补自选/市场周期切换。
EOF
)"
```

---

## Spec coverage (self-review)

| Spec | Task |
|------|------|
| §1 404 文案 | 1 |
| §2 双页 UI / limit / 空态 / 切标的保留 | 3 |
| §3 CandleChart | 2 |
| §4 测试文档验收 | 1 + 4 |

无 TBD；非目标未列入实现步骤。
