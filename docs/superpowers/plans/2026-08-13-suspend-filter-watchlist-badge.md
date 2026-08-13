# 停牌硬过滤 + 自选角标 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 有当日停牌数据时硬过滤真剔除；自选名称旁标「停」；无数据时宽松不误杀。

**Architecture:** `suspend.load_suspended_vt_symbols`；`apply_hard_filters(..., suspended_vts=)`；engine/pattern/leader/peer 传入；自选 enrich 加 `suspended`。

**Tech Stack:** FastAPI · SQLAlchemy · Vue 3 · pytest

**Spec:** `docs/superpowers/specs/2026-08-13-suspend-filter-watchlist-badge-design.md`

## Global Constraints

- 无当日停牌行 / `suspended_vts` 空或 None → 不剔除
- `exclude_suspended=false` → 不剔除
- QuoteRow 比较统一 vt（TF→vt）
- 不改 Ops sync；不新增表列
- Commit 简体中文；不 push

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/suspend.py` | 加载当日停牌 vt set |
| `backend/app/services/hard_filters.py` | 扩参剔除 |
| `backend/app/services/engine.py` 等 | 传入 suspended_vts |
| `backend/app/api/v1/watchlist.py` + schema | `suspended` 字段 |
| `frontend/.../WatchlistView.vue` + api | 「停」标签 |
| `backend/tests/test_suspend*.py` | 单测 |
| docs | roadmap #44 + smoke |

---

### Task 1: suspend 服务 + hard_filters 扩参

**Files:**
- Create: `backend/app/services/suspend.py`
- Modify: `backend/app/services/hard_filters.py`
- Create: `backend/tests/test_suspend_filter.py`

**Interfaces:**
- `resolve_suspend_cal_date(db) -> str`
- `load_suspended_vt_symbols(db, cal_date: str | None = None) -> set[str]`
- `apply_hard_filters(rows, prefs, *, suspended_vts: set[str] | None = None)`

- [ ] **Step 1: 写失败测**

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.schemas.screener import HardFilterPrefs
from app.services.hard_filters import apply_hard_filters
from app.services.quotes import QuoteRow
from app.services import suspend as sus


def _row(tf: str, name: str = "x") -> QuoteRow:
    return QuoteRow(symbol=tf, name=name, amount=1e9, total_mv=1e6)


def test_load_empty() -> None:
    db = MagicMock()
    db.execute.return_value = MagicMock(mappings=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    # 简化 side_effect：
    res = MagicMock()
    res.mappings.return_value.all.return_value = []
    db.execute.return_value = res
    with patch("app.services.suspend.latest_open_yyyymmdd", return_value="20260813"):
        assert sus.load_suspended_vt_symbols(db) == set()


def test_load_maps_vt() -> None:
    db = MagicMock()
    res = MagicMock()
    res.mappings.return_value.all.return_value = [
        {"symbol": "000001", "exchange": "SZSE", "cal_date": "2026-08-13", "suspend_type": "S"},
    ]
    db.execute.return_value = res
    out = sus.load_suspended_vt_symbols(db, "2026-08-13")
    assert out == {"000001.SZSE"}


def test_filter_excludes_when_set() -> None:
    prefs = HardFilterPrefs(
        exclude_st=False,
        exclude_suspended=True,
        min_amount_wan=0,
        min_total_mv_yi=0,
        exclude_new_listing=False,
        exclude_limit_board=False,
    )
    rows = [_row("SZSE.000001"), _row("SHSE.600519")]
    out = apply_hard_filters(rows, prefs, suspended_vts={"000001.SZSE"})
    assert [r.symbol for r in out] == ["SHSE.600519"]


def test_filter_lenient_empty_set() -> None:
    prefs = HardFilterPrefs(
        exclude_st=False,
        exclude_suspended=True,
        min_amount_wan=0,
        min_total_mv_yi=0,
        exclude_new_listing=False,
        exclude_limit_board=False,
    )
    rows = [_row("SZSE.000001")]
    assert len(apply_hard_filters(rows, prefs, suspended_vts=set())) == 1
    assert len(apply_hard_filters(rows, prefs, suspended_vts=None)) == 1


def test_filter_respects_exclude_false() -> None:
    prefs = HardFilterPrefs(
        exclude_st=False,
        exclude_suspended=False,
        min_amount_wan=0,
        min_total_mv_yi=0,
        exclude_new_listing=False,
        exclude_limit_board=False,
    )
    rows = [_row("SZSE.000001")]
    assert len(apply_hard_filters(rows, prefs, suspended_vts={"000001.SZSE"})) == 1
```

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && uv run pytest tests/test_suspend_filter.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现**

`suspend.py`：

```python
"""当日停牌 vt 集合（读 app.symbol_suspend_days）。"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.symbols import to_vt_symbol
from app.services.tushare_screener import latest_open_yyyymmdd


def resolve_suspend_cal_date(db: Session) -> str:
    ymd = latest_open_yyyymmdd(db)
    s = str(ymd or "").replace("-", "")[:8]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def load_suspended_vt_symbols(db: Session, cal_date: str | None = None) -> set[str]:
    day = cal_date or resolve_suspend_cal_date(db)
    rows = db.execute(
        text(
            """
            SELECT symbol, exchange
            FROM app.symbol_suspend_days
            WHERE cal_date = :d
            """
        ),
        {"d": day},
    ).mappings().all()
    out: set[str] = set()
    for r in rows:
        sym = str(r.get("symbol") or "").strip()
        exch = str(r.get("exchange") or "").strip()
        if sym and exch:
            out.add(to_vt_symbol(sym, exch))
    return out
```

`hard_filters.py` — 在 `apply_hard_filters` 签名加 `suspended_vts: set[str] | None = None`，循环内 ST 等逻辑后加：

```python
    from app.services.quotes import _to_vt_symbol  # 或文件顶 import

    # ... existing loop ...
        if prefs.exclude_suspended and suspended_vts:
            vt = _to_vt_symbol(row.symbol)
            if vt in suspended_vts:
                continue
```

（放在 append 之前；保持「缺字段跳过」注释改为说明依赖 suspended_vts。）

- [ ] **Step 4: 跑测通过**

Run: `cd backend && uv run pytest tests/test_suspend_filter.py tests/test_engine.py tests/test_hard_filters_resolve.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/suspend.py backend/app/services/hard_filters.py backend/tests/test_suspend_filter.py
git commit -m "$(cat <<'EOF'
feat(screener): 硬过滤接入当日停牌表

有数据时剔除；空集宽松不误杀。
EOF
)"
```

---

### Task 2: 选股调用方传入 suspended_vts

**Files:**
- Modify: `backend/app/services/engine.py`
- Modify: `backend/app/services/pattern_screen.py`
- Modify: `backend/app/services/leader_screen.py`
- Modify: `backend/app/services/reference_peer.py`

**Interfaces:**
- 凡 `apply_hard_filters(rows, prefs)` 且函数有 `db`：改为  
  `apply_hard_filters(rows, prefs, suspended_vts=load_suspended_vt_symbols(db))`  
- 可抽局部：`suspended = load_suspended_vt_symbols(db)` 同函数内复用多次调用

- [ ] **Step 1: 定位全部调用**

Run: `rg -n "apply_hard_filters\\(" backend/app/services`

- [ ] **Step 2: 逐文件传入**

每文件顶：

```python
from app.services.suspend import load_suspended_vt_symbols
```

每个有 `db` 的筛选函数开头（或首次 filter 前）：

```python
    suspended_vts = load_suspended_vt_symbols(db)
```

所有 `apply_hard_filters(..., prefs)` → `apply_hard_filters(..., prefs, suspended_vts=suspended_vts)`。

- [ ] **Step 3: 回归测**

Run: `cd backend && uv run pytest tests/test_engine.py tests/test_leader_screen.py tests/test_presets_d.py tests/test_recipe_weights.py tests/test_resonance_screen.py -q`  
Expected: PASS（mock 路径下 load 可能打真 SQL——若失败，对 load 做 patch 或确保 MagicMock execute 返回空 all）

若集成测因 `load_suspended_vt_symbols` 调真实 execute 失败：在相关测里  
`patch("app.services.engine.load_suspended_vt_symbols", return_value=set())`  
或让 MagicMock 的 `mappings().all()` 默认 `[]`。

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/engine.py backend/app/services/pattern_screen.py backend/app/services/leader_screen.py backend/app/services/reference_peer.py backend/tests
git commit -m "$(cat <<'EOF'
feat(screener): 选股路径传入停牌集合

engine/形态/龙头/对标统一消费当日停牌。
EOF
)"
```

---

### Task 3: 自选 suspended 字段 + 「停」标签

**Files:**
- Modify: `backend/app/schemas/watchlist.py` — `WatchlistItemOut.suspended: bool = False`
- Modify: `backend/app/api/v1/watchlist.py` — `_enrich` 打标
- Modify: `frontend/src/api/watchlist.ts` — 类型
- Modify: `frontend/src/views/WatchlistView.vue` — 名称旁标签
- Modify: `backend/tests/test_suspend_filter.py` 或新建 enrich 测

- [ ] **Step 1: enrich 测（可选轻量）**

若 `_enrich` 难单测，可测「给定 suspended set 与 items 的布尔映射」纯函数；或 API 级 mock。最低：schema 默认 False 的构造测可省略，重点前端+手工。

建议在 `test_suspend_filter.py` 加：

```python
def test_watchlist_item_default_suspended() -> None:
    from app.schemas.watchlist import WatchlistItemOut
    item = WatchlistItemOut(
        symbol="000001",
        exchange="SZSE",
        name="平安",
        sort_order=0,
        vt_symbol="000001.SZSE",
        tf_symbol="SZSE.000001",
    )
    assert item.suspended is False
```

- [ ] **Step 2: `_enrich` 打标**

```python
from app.services.suspend import load_suspended_vt_symbols

def _enrich(...):
    suspended = load_suspended_vt_symbols(db) if db is not None else set()
    ...
        vt = to_vt_symbol(item.symbol, item.exchange)
        out.append(
            WatchlistItemOut(
                ...
                suspended=vt in suspended,
            )
        )
```

- [ ] **Step 3: 前端**

`watchlist.ts` `WatchlistItem` 加 `suspended?: boolean`。

列表名称单元格（约 `item.name`）：

```vue
<td>
  {{ item.name || '—' }}
  <span v-if="item.suspended" class="suspend-tag" title="停牌">停</span>
</td>
```

详情头 `selected` 旁同样可选。

CSS：

```css
.suspend-tag {
  margin-left: 4px;
  font-size: 0.7rem;
  padding: 0 4px;
  border-radius: 0.25rem;
  border: 1px solid var(--border);
  color: var(--danger, #b42318);
}
```

- [ ] **Step 4: build + pytest**

Run: `cd frontend && npm run build`  
Run: `cd backend && uv run pytest tests/test_suspend_filter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/watchlist.py backend/app/api/v1/watchlist.py frontend/src/api/watchlist.ts frontend/src/views/WatchlistView.vue backend/tests/test_suspend_filter.py
git commit -m "$(cat <<'EOF'
feat(watchlist): 列表名称旁标记当日停牌

enrich 读停牌表；无数据不标。
EOF
)"
```

---

### Task 4: 文档与总验收

**Files:**
- Modify: `docs/product-roadmap.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: 路线图**

在 #43 后：

```markdown
44. ~~停牌硬过滤与自选角标~~（已完成 → [spec](./superpowers/specs/2026-08-13-suspend-filter-watchlist-badge-design.md)）
```

- [ ] **Step 2: smoke**

```markdown
- [ ] Ops 已 `sync_suspend_daily` 后：Hub 硬过滤「排除停牌」结果不含当日停牌票；`/watchlist` 停牌标的名称旁见「停」；未同步停牌表时选股不因停牌误杀、列表无「停」
```

- [ ] **Step 3: check.sh**

Run: `./scripts/check.sh`  
Expected: 绿

- [ ] **Step 4: Commit**

```bash
git add docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录停牌硬过滤与自选角标完成

更新路线图 #44 与 smoke 验收项。
EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| suspend load | 1 |
| hard_filters 语义 | 1 |
| 选股调用方 | 2 |
| 自选 suspended + UI | 3 |
| docs | 4 |

无 TBD。
