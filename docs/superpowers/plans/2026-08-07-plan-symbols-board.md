# 自选 · 当日计划对照卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 自选策略区展示当日 active 计划标的三态（持仓 / 自选 / 仅计划），与「计划外」对照。

**Architecture:** 扩展 `load_active_plan_snapshot` 保留 `sort_order` 有序列表 → 纯函数 `build_plan_symbol_statuses` 组装三态 → 写入 `risk_summary.plan_symbols` → Watchlist 风控卡与通知历史之间只读对照卡。

**Tech Stack:** FastAPI、现有 TradingPlan ORM、Vue WatchlistView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-plan-symbols-board-design.md`

## Global Constraints

- 只改 zak2；共用 PG，不改 zak 代码
- 只读；无计划 CRUD / 下单 / 一键加自选
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/off_plan.py` | snapshot 增加 `ordered_vt_symbols`；`build_plan_symbol_statuses` |
| `backend/app/services/strategy_board.py` | `risk_summary.plan_symbols` |
| `backend/app/schemas/watchlist.py` | `PlanSymbolStatus` + `RiskSummaryOut.plan_symbols` |
| `backend/tests/test_off_plan.py` | 组装纯函数单测 |
| `backend/tests/test_strategy_board.py` | board 三态 / 无计划 |
| `frontend/src/api/watchlist.ts` | `PlanSymbolStatus` + `RiskSummary.plan_symbols` |
| `frontend/src/views/WatchlistView.vue` | 「当日计划」对照卡 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: off_plan — ordered snapshot + build_plan_symbol_statuses

**Files:**
- Modify: `backend/app/services/off_plan.py`
- Modify: `backend/tests/test_off_plan.py`

**Interfaces:**
- `load_active_plan_snapshot(...) -> dict | None` 增加字段：
  - `ordered_vt_symbols: list[str]` — 按 `TradingPlanSymbol.sort_order`，去重保序
  - 既有 `vt_symbols: set[str]`、`max_position_pct`、`trade_date` 不变
- `build_plan_symbol_statuses(*, ordered_vt_symbols: list[str], watchlist_vts: set[str], position_vts: set[str], name_by_vt: dict[str, str]) -> list[dict]`
  - 每项：`{vt_symbol, name, in_watchlist, in_position}`
  - `name` = `name_by_vt.get(vt, "")`
  - `in_watchlist` = `vt in watchlist_vts`
  - `in_position` = `vt in position_vts`
  - 无序列 → `[]`

- [ ] **Step 1: 写失败单测**

在 `backend/tests/test_off_plan.py` 追加：

```python
from app.services.off_plan import build_plan_symbol_statuses, list_off_plan_vt_symbols


def test_build_plan_symbol_statuses_empty() -> None:
    assert (
        build_plan_symbol_statuses(
            ordered_vt_symbols=[],
            watchlist_vts=set(),
            position_vts=set(),
            name_by_vt={},
        )
        == []
    )


def test_build_plan_symbol_statuses_three_states() -> None:
    rows = build_plan_symbol_statuses(
        ordered_vt_symbols=["600519.SSE", "000001.SZSE", "300750.SZSE"],
        watchlist_vts={"600519.SSE", "000001.SZSE"},
        position_vts={"600519.SSE"},
        name_by_vt={"600519.SSE": "茅台", "000001.SZSE": "平安"},
    )
    assert rows == [
        {
            "vt_symbol": "600519.SSE",
            "name": "茅台",
            "in_watchlist": True,
            "in_position": True,
        },
        {
            "vt_symbol": "000001.SZSE",
            "name": "平安",
            "in_watchlist": True,
            "in_position": False,
        },
        {
            "vt_symbol": "300750.SZSE",
            "name": "",
            "in_watchlist": False,
            "in_position": False,
        },
    ]
```

- [ ] **Step 2: RED**

Run: `cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_off_plan.py::test_build_plan_symbol_statuses_three_states -v`  
Expected: FAIL（`build_plan_symbol_statuses` 未定义）

- [ ] **Step 3: 实现**

改 `load_active_plan_snapshot` 的 return（symbols 已按 sort_order 查询）：

```python
ordered: list[str] = []
seen: set[str] = set()
for s in symbols:
    vt = to_vt_symbol(s.symbol, s.exchange)
    if vt in seen:
        continue
    seen.add(vt)
    ordered.append(vt)
return {
    "vt_symbols": set(ordered),
    "ordered_vt_symbols": ordered,
    "max_position_pct": float(plan.max_position_pct or 0),
    "trade_date": str(plan.trade_date or trade_date),
}
```

新增：

```python
def build_plan_symbol_statuses(
    *,
    ordered_vt_symbols: list[str],
    watchlist_vts: set[str],
    position_vts: set[str],
    name_by_vt: dict[str, str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for vt in ordered_vt_symbols:
        out.append(
            {
                "vt_symbol": vt,
                "name": name_by_vt.get(vt, "") or "",
                "in_watchlist": vt in watchlist_vts,
                "in_position": vt in position_vts,
            }
        )
    return out
```

- [ ] **Step 4: GREEN**

Run: `cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_off_plan.py -v`  
Expected: PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: strategy_board + schema + board 单测

**Files:**
- Modify: `backend/app/services/strategy_board.py`
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/tests/test_strategy_board.py`

**Interfaces:**
- Consumes: `build_plan_symbol_statuses`；snapshot 的 `ordered_vt_symbols`（mock 无此键时用 `sorted(vt_symbols)` 兜底，便于旧 mock）
- Produces: `risk_summary["plan_symbols"]`
- Schema:
  - `PlanSymbolStatus(vt_symbol: str, name: str = "", in_watchlist: bool = False, in_position: bool = False)`
  - `RiskSummaryOut.plan_symbols: list[PlanSymbolStatus] = Field(default_factory=list)`

- [ ] **Step 1: 写失败单测**

在 `test_load_strategy_board_empty` 断言追加：

```python
assert rs["plan_symbols"] == []
```

在 `test_load_strategy_board_risk_summary_with_off_plan` 的 snapshot mock 改为：

```python
return_value={
    "vt_symbols": {"600519.SSE", "300750.SZSE"},
    "ordered_vt_symbols": ["600519.SSE", "300750.SZSE"],
    "max_position_pct": 80.0,
    "trade_date": "2026-08-05",
},
```

并让 `list_items` 返回一只自选（600519），例如用简易 namespace：

```python
from types import SimpleNamespace

# patch list_items:
return_value=[
    SimpleNamespace(symbol="600519", exchange="SSE", name="茅台"),
],
```

断言：

```python
assert rs["plan_symbols"] == [
    {
        "vt_symbol": "600519.SSE",
        "name": "茅台",
        "in_watchlist": True,
        "in_position": True,
    },
    {
        "vt_symbol": "300750.SZSE",
        "name": "",
        "in_watchlist": False,
        "in_position": False,
    },
]
```

（持仓 mock 已含 600519 + 000001；300750 仅计划 →「仅计划」态。）

- [ ] **Step 2: RED**

Run: `cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_strategy_board.py::test_load_strategy_board_empty tests/test_strategy_board.py::test_load_strategy_board_risk_summary_with_off_plan -v`  
Expected: FAIL（缺 `plan_symbols`）

- [ ] **Step 3: Schema**

在 `RiskSummaryOut` 前增加：

```python
class PlanSymbolStatus(BaseModel):
    vt_symbol: str
    name: str = ""
    in_watchlist: bool = False
    in_position: bool = False
```

`RiskSummaryOut` 增加：

```python
plan_symbols: list[PlanSymbolStatus] = Field(default_factory=list)
```

- [ ] **Step 4: strategy_board 组装**

Import：

```python
from app.services.off_plan import (
    build_plan_symbol_statuses,
    list_off_plan_vt_symbols,
    load_active_plan_snapshot,
)
```

在构建 `risk_summary` 前：

```python
if plan_snap is None:
    ordered_plan = []
else:
    ordered_plan = list(plan_snap.get("ordered_vt_symbols") or [])
    if not ordered_plan:
        ordered_plan = sorted(plan_snap.get("vt_symbols") or [])

plan_symbols = build_plan_symbol_statuses(
    ordered_vt_symbols=ordered_plan,
    watchlist_vts=set(watchlist_vts),
    position_vts=set(position_vts),
    name_by_vt={k: (v or "") for k, v in name_by_vt.items()},
)
```

`risk_summary` 增加：

```python
"plan_symbols": plan_symbols,
```

- [ ] **Step 5: GREEN**

Run: `cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_strategy_board.py tests/test_off_plan.py -v`  
Expected: PASS

- [ ] **Step 6: Commit** — 跳过

---

### Task 3: 前端对照卡 + 类型

**Files:**
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`

**Interfaces:**
- Consumes: `board.risk_summary.plan_symbols`
- Produces: 只读 UI；点击行/`vt` 调用现有 `selectVt(vt)`

- [ ] **Step 1: 类型**

```typescript
export type PlanSymbolStatus = {
  vt_symbol: string
  name: string
  in_watchlist: boolean
  in_position: boolean
}

export type RiskSummary = {
  total_capital: number | null
  actual_position_pct: number | null
  plan_max_pct: number | null
  off_plan_count: number
  off_plan_symbols: string[]
  active_plan_date: string
  plan_symbols: PlanSymbolStatus[]
}
```

- [ ] **Step 2: WatchlistView — script**

在既有 `riskSummary` computed 旁增加：

```typescript
const planSymbols = computed(() => riskSummary.value?.plan_symbols ?? [])

function planSymbolLabel(row: { in_position: boolean; in_watchlist: boolean }): string {
  if (row.in_position) return '持仓'
  if (row.in_watchlist) return '自选'
  return '仅计划'
}
```

（若用 `PlanSymbolStatus` 类型，从 `@/api/watchlist` import。）

- [ ] **Step 3: WatchlistView — template**

插在风控卡片 `</div>`（`.risk-card`）之后、通知历史 `.notify-card` 之前：

```vue
<div class="pos-form plan-card">
  <h3>
    当日计划
    <span class="muted" v-if="riskSummary?.active_plan_date">
      {{ riskSummary.active_plan_date }}
    </span>
  </h3>
  <p v-if="!planSymbols.length" class="muted">当日无 active 计划</p>
  <ul v-else class="plan-list">
    <li
      v-for="row in planSymbols"
      :key="row.vt_symbol"
      :class="{ on: selected?.vt_symbol === row.vt_symbol }"
      @click="selectVt(row.vt_symbol)"
    >
      <button type="button" class="chip-link mono" @click.stop="selectVt(row.vt_symbol)">
        {{ row.vt_symbol }}
      </button>
      <span class="plan-name">{{ row.name || '—' }}</span>
      <span class="plan-tag">{{ planSymbolLabel(row) }}</span>
    </li>
  </ul>
</div>
```

- [ ] **Step 4: 样式**（贴近 notify-card，勿大改主题）

```css
.plan-card {
  margin-top: 10px;
  margin-bottom: 0;
}
.plan-card h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.plan-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}
.plan-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 6px;
  cursor: pointer;
}
.plan-list li:hover,
.plan-list li.on {
  background: rgba(255, 255, 255, 0.04);
}
.plan-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.85rem;
}
.plan-tag {
  font-size: 0.75rem;
  color: var(--muted, #8b98a8);
  flex-shrink: 0;
}
```

- [ ] **Step 5: build**

Run: `cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build`  
Expected: 成功（无 TS 错误）

- [ ] **Step 6: Commit** — 跳过

---

### Task 4: 文档 + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap**

总览「守则 / 笔记 / 信息流」备注改为含：自选可见当日计划对照。

看盘表「仓位与风控偏好」或新增一行：

| 当日计划对照 | **有**（薄） | `risk_summary.plan_symbols`；自选/持仓/仅计划三态；只读 |

「风控通知 / 交易链路」备注可带一句：自选可见计划标的对照。

- [ ] **Step 2: smoke**

§3 自选条目追加：风控与通知之间可见**当日计划**（空态或三态标签；点行可选中）。

- [ ] **Step 3: 全量**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest -q
cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build
```

Expected: pytest 全绿；build 成功。

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage（自检）

| Spec 项 | Task |
|---------|------|
| `plan_symbols` API 字段与组装规则 | 1–2 |
| `sort_order` 有序 | 1（ordered_vt_symbols） |
| 无计划 → `[]` | 1–2 |
| UI 位置 / 三态标签 / selectVt / 只读 | 3 |
| pytest + build / gap / smoke | 2–4 |
| 非目标（CRUD/下单/守则大改） | 未实现（符合） |
