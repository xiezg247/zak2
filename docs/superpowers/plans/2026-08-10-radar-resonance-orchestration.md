# 共振编排加深（Hub 雷达共振 + 卡片 ★）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** Hub 内置配方 `radar_resonance` 将跨卡共振结果写入 `screener_runs`；Radar 明细对出现在 ≥2 张卡的标的显示 ★。

**Architecture:** 仿 `radar_leader`：`presets` 注册 builtin → `engine.run_recipe_screen` 分支 → `resonance_screen.run_resonance_screen` 调既有 `list_radar_resonance`，映射为 `QuoteRow` 后 `_pack_result`。前端 Hub 靠 recipes API 自动出项；Radar 用侧栏共振 entries 建 vt→card_count 给明细表打 ★。

**Tech Stack:** FastAPI、SQLAlchemy Session、既有 `radar_resonance` / `engine._pack_result`、Vue3 RadarView / ScreenerHubView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-radar-resonance-orchestration-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不改共振权重算法；不新增独立 `POST /runs/resonance`
- 无计划草案
- 硬过滤：本刀**跳过**（spec 允许）；config 仍写入 `hard_filter_resolved` 供审计
- Commit 仅用户明确要求时（默认跳过各 Task 的 Commit 步）
- 不打真网

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/presets.py` | 注册 builtin `radar_resonance` |
| `backend/app/services/resonance_screen.py` | **新建** `run_resonance_screen` |
| `backend/app/services/engine.py` | `run_recipe_screen` 分支转调 |
| `backend/tests/test_resonance_screen.py` | **新建** 注册 / 无卡 400 / 有 entries / 空 entries |
| `frontend/src/views/RadarView.vue` | 「共振选股 → Hub」+ 明细 ★ |
| `frontend/src/views/ScreenerHubView.vue` | query `radar_resonance` 时 topN=20（可选小改） |
| `docs/gap-vs-desktop.md` / `docs/smoke-checklist.md` | 文档 |

---

### Task 1: builtin + `run_resonance_screen` + engine 分支

**Files:**
- Create: `backend/app/services/resonance_screen.py`
- Create: `backend/tests/test_resonance_screen.py`
- Modify: `backend/app/services/presets.py`（在 `radar_leader` 条目后追加）
- Modify: `backend/app/services/engine.py`（`radar_leader` 分支旁增加 `radar_resonance`）

**Interfaces:**
- Consumes: `list_radar_resonance(db, user_id=..., min_cards=2, top_n=...)`；`parse_flexible_symbol` / `to_tf_symbol`；`QuoteRow`；`engine._pack_result`
- Produces:
  - `run_resonance_screen(*, db: Session, user_id: str, top_n: int = 20, hard_filter: HardFilterPrefs, previous_symbols: set[str] | None = None) -> dict[str, Any]`
  - 结果：`source == "radar_resonance"`；`condition` 以「雷达共振」开头（空结果可含「暂无共振」）；`config` 含 `recipe_id/top_n/min_cards`
  - 行字段：经 `_pack_result` 的 `vt_symbol/name/change_pct/last_price/score`；`hit_reason` 如 `共振 加权3.0：选股·龙头、发现·连板梯队`；`seal_time_label` 若有则写入 packed 行（见 Step 3）

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_resonance_screen.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.market import RadarResonanceEntry, RadarResonanceOut
from app.schemas.screener import HardFilterPrefs, RecipeRunRequest
from app.services.engine import run_recipe_screen
from app.services.presets import get_builtin_recipe


def test_radar_resonance_recipe_registered() -> None:
    recipe = get_builtin_recipe("radar_resonance")
    assert recipe is not None
    assert recipe.implemented is True
    assert recipe.name == "雷达共振"
    assert recipe.top_n == 20


def test_run_resonance_no_cards_raises_400() -> None:
    db = MagicMock()
    with patch(
        "app.services.resonance_screen.list_radar_cards",
        return_value=[],
    ):
        from app.services.resonance_screen import run_resonance_screen

        with pytest.raises(HTTPException) as ei:
            run_resonance_screen(
                db=db,
                user_id="u1",
                top_n=20,
                hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
            )
        assert ei.value.status_code == 400
        assert "雷达卡片" in str(ei.value.detail)


def test_run_resonance_with_entries() -> None:
    db = MagicMock()
    entries = [
        RadarResonanceEntry(
            vt_symbol="600519.SSE",
            name="茅台",
            card_count=3,
            card_titles=["选股·龙头", "发现·连板梯队"],
            resonance_score=2.9,
            change_pct=2.0,
            last_price=1800.0,
            seal_time_label="09:30 封板",
        )
    ]
    out = RadarResonanceOut(min_cards=2, top_n=20, total=1, entries=entries)
    with (
        patch("app.services.resonance_screen.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.resonance_screen.list_radar_resonance", return_value=out) as lr,
    ):
        from app.services.resonance_screen import run_resonance_screen

        result = run_resonance_screen(
            db=db,
            user_id="u1",
            top_n=12,
            hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
        )
    lr.assert_called_once()
    assert lr.call_args.kwargs["user_id"] == "u1"
    assert lr.call_args.kwargs["top_n"] == 12
    assert lr.call_args.kwargs["min_cards"] == 2
    assert result["source"] == "radar_resonance"
    assert result["row_count"] == 1
    assert "雷达共振" in result["condition"]
    row = result["rows"][0]
    assert row["vt_symbol"] == "600519.SSE"
    assert row["score"] == 2.9
    assert "共振" in row["hit_reason"]
    assert "选股·龙头" in row["hit_reason"]
    assert row.get("seal_time_label") == "09:30 封板"
    assert result["config"]["recipe_id"] == "radar_resonance"
    assert result["config"]["min_cards"] == 2


def test_run_resonance_empty_entries_ok() -> None:
    db = MagicMock()
    out = RadarResonanceOut(min_cards=2, top_n=20, total=0, entries=[])
    with (
        patch("app.services.resonance_screen.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.resonance_screen.list_radar_resonance", return_value=out),
    ):
        from app.services.resonance_screen import run_resonance_screen

        result = run_resonance_screen(
            db=db,
            user_id="u1",
            top_n=20,
            hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
        )
    assert result["source"] == "radar_resonance"
    assert result["row_count"] == 0
    assert "暂无共振" in result["condition"]


def test_run_recipe_screen_radar_resonance_branch() -> None:
    fake = {
        "condition": "雷达共振",
        "source": "radar_resonance",
        "row_count": 0,
        "total_scanned": 0,
        "config": {},
        "rows": [],
        "industry_dist": [],
        "diff": None,
    }
    with patch("app.services.resonance_screen.run_resonance_screen", return_value=fake) as run:
        result = run_recipe_screen(
            RecipeRunRequest(
                recipe_id="radar_resonance",
                top_n=20,
                hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
            ),
            db=MagicMock(),
            user_id="u1",
        )
    assert result["source"] == "radar_resonance"
    run.assert_called_once()
    assert run.call_args.kwargs["user_id"] == "u1"


def test_run_recipe_screen_resonance_requires_user() -> None:
    with pytest.raises(HTTPException) as ei:
        run_recipe_screen(
            RecipeRunRequest(
                recipe_id="radar_resonance",
                hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
            ),
            db=MagicMock(),
            user_id=None,
        )
    assert ei.value.status_code == 400
```

- [ ] **Step 2: 跑测确认 RED**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_resonance_screen.py -q
```

Expected: FAIL（模块/recipe 不存在）

- [ ] **Step 3: 实现**

`presets.py` 在 `radar_leader` 后追加：

```python
    BuiltinRecipeOut(
        recipe_id="radar_resonance",
        name="雷达共振",
        trigger_kind="intraday",
        top_n=20,
        implemented=True,
    ),
```

`resonance_screen.py`（完整骨架）：

```python
"""雷达共振配方：跨卡共振 → screener_runs。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.screener import HardFilterPrefs
from app.services.quotes import QuoteRow
from app.services.radar import list_radar_cards
from app.services.radar_resonance import list_radar_resonance
from app.services.symbols import parse_flexible_symbol, to_tf_symbol


def _entry_to_quote_row(entry) -> QuoteRow:
    code, exch = parse_flexible_symbol(entry.vt_symbol)
    tf = to_tf_symbol(code, exch)
    row = QuoteRow(
        symbol=tf,
        name=entry.name or "",
        change_pct=float(entry.change_pct or 0.0),
        last_price=float(entry.last_price or 0.0),
    )
    titles = "、".join(entry.card_titles) if entry.card_titles else f"{entry.card_count}卡"
    row.__dict__["_score"] = float(entry.resonance_score)
    row.__dict__["_hit_reason"] = f"共振 加权{entry.resonance_score:g}：{titles}"
    if entry.seal_time_label:
        row.__dict__["_seal_time_label"] = entry.seal_time_label
    return row


def run_resonance_screen(
    *,
    db: Session,
    user_id: str,
    top_n: int = 20,
    hard_filter: HardFilterPrefs,
    previous_symbols: set[str] | None = None,
) -> dict[str, Any]:
    from app.services.engine import _pack_result

    if not user_id:
        raise HTTPException(status_code=400, detail="雷达共振需要登录用户")
    cards = list_radar_cards(db)
    if not cards:
        raise HTTPException(status_code=400, detail="暂无雷达卡片，请先打开雷达页刷新")

    resonance = list_radar_resonance(db, user_id=user_id, min_cards=2, top_n=top_n)
    quote_rows = [_entry_to_quote_row(e) for e in resonance.entries]
    # 本刀跳过硬过滤（spec 允许）
    condition = "雷达共振"
    if not quote_rows:
        condition = "雷达共振 · 暂无共振（跨卡≥2）"

    result = _pack_result(
        quote_rows,
        total_scanned=len(quote_rows),
        condition=condition,
        source="radar_resonance",
        config={
            "recipe_id": "radar_resonance",
            "top_n": top_n,
            "min_cards": 2,
            "hard_filter_skipped": True,
        },
        previous_symbols=previous_symbols,
        hard_filter=hard_filter,
    )
    for packed, src in zip(result["rows"], quote_rows, strict=True):
        label = src.__dict__.get("_seal_time_label")
        if label:
            packed["seal_time_label"] = label
    return result
```

`engine.py` 在 `radar_leader` 分支后：

```python
    if recipe.recipe_id == "radar_resonance":
        from app.services import resonance_screen

        if db is None or not user_id:
            raise HTTPException(status_code=400, detail="雷达共振需要数据库与登录用户")
        return resonance_screen.run_resonance_screen(
            db=db,
            user_id=user_id,
            top_n=top_n,
            hard_filter=prefs,
            previous_symbols=previous_symbols,
        )
```

注意：`_pack_result` 的 `config` 会再 merge `hard_filter_resolved`；测试断言 `config["recipe_id"]` / `min_cards` 即可。

- [ ] **Step 4: GREEN**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_resonance_screen.py -q
```

Expected: PASS

- [ ] **Step 5: Commit** — 跳过（除非用户要求）

---

### Task 2: Radar UI（★ + 跳转 Hub）与 Hub query

**Files:**
- Modify: `frontend/src/views/RadarView.vue`
- Modify: `frontend/src/views/ScreenerHubView.vue`（`onMounted` query 分支）

**Interfaces:**
- Consumes: 已有 `resonance: RadarResonanceEntry[]`（含 `vt_symbol` / `card_count`）
- Produces:
  - `goResonanceScreen()` → `/screener?recipe=radar_resonance`
  - `cardCountByVt: Map` 或 computed `Record<string, number>`
  - `rowCardCount(row)`：从 `row.vt_symbol` / `row.tf_symbol` / 可解析 symbol 查 map；`≥2` 显示 ★
  - Hub：`qRecipe === 'radar_resonance'` 时 `topN = 20`

- [ ] **Step 1: RadarView**

在 script 增加：

```ts
const cardCountByVt = computed(() => {
  const m = new Map<string, number>()
  for (const e of resonance.value) {
    m.set(e.vt_symbol, e.card_count)
    // 兼容 TF 风格 key（若卡片行用 tf_symbol）
    const s = e.vt_symbol
    if (s.includes('.')) {
      const [a, b] = s.split('.')
      // 600519.SSE ↔ SHSE.600519 粗映射供明细查
      if (b === 'SSE') m.set(`SHSE.${a}`, e.card_count)
      else if (b === 'SZSE') m.set(`SZSE.${a}`, e.card_count)
      else if (b === 'BSE') m.set(`BJSE.${a}`, e.card_count)
      else if (a === 'SHSE' || a === 'SZSE' || a === 'BJSE') m.set(`${b}.${a === 'SHSE' ? 'SSE' : a === 'BJSE' ? 'BSE' : 'SZSE'}`, e.card_count)
    }
  }
  return m
})

function rowVtKeys(row: Record<string, unknown>): string[] {
  const keys: string[] = []
  for (const k of ['vt_symbol', 'tf_symbol', 'symbol'] as const) {
    const v = String(row[k] || '').trim()
    if (v) keys.push(v)
  }
  return keys
}

function rowResonanceCount(row: Record<string, unknown>): number {
  for (const k of rowVtKeys(row)) {
    const n = cardCountByVt.value.get(k)
    if (typeof n === 'number') return n
  }
  return 0
}

function goResonanceScreen() {
  void router.push({ path: '/screener', query: { recipe: 'radar_resonance' } })
}
```

工具栏在「龙头选股 → Hub」旁加：

```html
<button class="primary" type="button" @click="goResonanceScreen">共振选股 → Hub</button>
```

（若两颗 primary 过重，共振可用 `ghost`，与「展开共振」同级即可——保持一主一次即可。）

明细表标的列：

```html
<td>
  <span v-if="rowResonanceCount(row) >= 2" class="star">★</span>
  {{ rowLabel(row) }}
</td>
```

侧栏可另加「共振选股 → Hub」按钮（可选，与龙头按钮并列）：

```html
<button class="primary full" type="button" @click="goResonanceScreen">共振选股 → Hub</button>
```

确认 `.star` 样式已存在（侧栏已用）；无需新 CSS。

- [ ] **Step 2: ScreenerHubView**

`onMounted` 内：

```ts
    if (qRecipe === 'radar_leader') topN.value = 12
    if (qRecipe === 'radar_resonance') topN.value = 20
```

配方下拉无需手写选项（来自 `list_builtin_recipes`）。确认 `isRadarLeader` 不会对 `radar_resonance` 显示 variant 控件（已按 `=== 'radar_leader'`）。

- [ ] **Step 3: 前端 build**

```bash
cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build
```

Expected: 成功

- [ ] **Step 4: Commit** — 跳过

---

### Task 3: gap / smoke + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap**

总览「市场 / 板块 / 雷达」备注：由「无完整共振编排」改为「Hub 雷达共振可落历史；仍无情绪+共振→计划草案」。

表格「共振侧栏」备注追加：`Hub 配方 radar_resonance 可落 screener_runs；明细 ≥2 卡 ★`。

- [ ] **Step 2: smoke**

§5 雷达条目追加/改写：

- Hub 可跑「雷达共振」并见历史  
- `/radar` 明细对多卡共振标的显示 ★  
- 「共振选股 → Hub」跳转 `recipe=radar_resonance`

- [ ] **Step 3: 全量 pytest**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest -q
```

Expected: 全绿（当前基线约 280+；本刀新增约 6）

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage（自检）

| Spec 要求 | Task |
|-----------|------|
| builtin `radar_resonance` | 1 |
| engine 分支 → `run_resonance_screen` | 1 |
| 无卡片 400 | 1 |
| 用户权重 via `list_radar_resonance` | 1 |
| 空 entries 成功 | 1 |
| `_pack_result` condition/source | 1 |
| 跳过硬过滤（注明） | 1（`hard_filter_skipped`） |
| Hub 下拉 / 跑 recipe | 1+2（API 自动 + query topN） |
| Radar ★ + 跳转 | 2 |
| gap / smoke | 3 |
| pytest + build | 2+3 |

## Placeholder scan

无 TBD / 「similar to Task N」未展开处。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-10-radar-resonance-orchestration.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每任务新子代理 + 任务间复审  
2. **Inline Execution** — 本会话按 executing-plans 连续执行并设检查点  

Which approach?
