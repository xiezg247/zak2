# 选股补全空行业（读 app.stock_industry）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 条件选股 / 普通配方 / 雷达龙头在硬过滤前，用 `app.stock_industry` 补全空 `QuoteRow.industry`。

**Architecture:** 读侧 `stock_industry`（load + enrich）→ `engine._maybe_enrich_industry` / `leader_screen` 在 `apply_hard_filters` 前调用；已有非空不覆盖。

**Tech Stack:** SQLAlchemy Session、`to_tf_symbol`、QuoteRow、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-enrich-empty-industry-design.md`

## Global Constraints

- 只改 zak2；不改 zak
- 不写 Redis；不改 sync job；不做行业下拉 API；不碰 `radar_resonance`
- Commit 仅用户明确要求时（默认跳过）
- 不打真网

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/stock_industry.py` | **新建** load + enrich |
| `backend/tests/test_stock_industry.py` | **新建** 单测 |
| `backend/app/services/engine.py` | `_maybe_enrich_industry` + 各硬过滤前调用 |
| `backend/app/services/leader_screen.py` | 候选池硬过滤前 enrich |
| `backend/tests/test_engine.py` 或 `test_leader_screen.py` | 集成级：mock map 后行业补全 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: `stock_industry` 读侧 + 单测

**Files:**
- Create: `backend/app/services/stock_industry.py`
- Create: `backend/tests/test_stock_industry.py`

**Interfaces:**
- `load_industry_map(db: Session) -> dict[str, str]`  
  - `SELECT symbol, exchange, industry FROM app.stock_industry`  
  - 键：`to_tf_symbol(symbol, exchange)`；空 industry 跳过  
  - 异常 / 表不存在 → 记日志可选，返回 `{}`  
- `enrich_empty_industries(rows: list[QuoteRow], mapping: dict[str, str]) -> int`  
- `enrich_rows_from_db(db: Session | None, rows: list[QuoteRow]) -> int`  
  - `db is None` → 0；否则 `enrich_empty_industries(rows, load_industry_map(db))`

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_stock_industry.py
from __future__ import annotations

from unittest.mock import MagicMock

from app.services import stock_industry as si
from app.services.quotes import QuoteRow


def _row(symbol: str, industry: str = "") -> QuoteRow:
    return QuoteRow(symbol=symbol, name="t", industry=industry)


def test_enrich_fills_empty_only() -> None:
    rows = [
        _row("SHSE.600519", ""),
        _row("SZSE.000001", "银行"),
        _row("SHSE.601318", ""),
    ]
    mapping = {"SHSE.600519": "白酒", "SZSE.000001": "覆盖不了", "SHSE.999999": "x"}
    n = si.enrich_empty_industries(rows, mapping)
    assert n == 1
    assert rows[0].industry == "白酒"
    assert rows[1].industry == "银行"
    assert rows[2].industry == ""


def test_load_industry_map_keys() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value = [
        {"symbol": "600519", "exchange": "SSE", "industry": "白酒"},
        {"symbol": "000001", "exchange": "SZSE", "industry": "银行"},
        {"symbol": "600000", "exchange": "SSE", "industry": ""},
    ]
    m = si.load_industry_map(db)
    assert m["SHSE.600519"] == "白酒"
    assert m["SZSE.000001"] == "银行"
    assert "SHSE.600000" not in m


def test_enrich_rows_from_db_none() -> None:
    assert si.enrich_rows_from_db(None, [_row("SHSE.1")]) == 0


def test_load_map_on_error_returns_empty() -> None:
    db = MagicMock()
    db.execute.side_effect = RuntimeError("no table")
    assert si.load_industry_map(db) == {}
```

- [ ] **Step 2: RED → 实现 → GREEN**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_stock_industry.py -q
```

- [ ] **Step 3: Commit** — 跳过

---

### Task 2: 挂载 engine + leader

**Files:**
- Modify: `backend/app/services/engine.py`
- Modify: `backend/app/services/leader_screen.py`
- Modify: `backend/tests/test_engine.py` 和/或 `test_leader_screen.py`

**Interfaces:**
- `engine._maybe_enrich_industry(db, rows) -> None` → 调 `stock_industry.enrich_rows_from_db`
- 在 **每一处** `apply_hard_filters(...)` 之前调用（`run_condition_screen` 各分支 + `run_recipe_screen` 普通配方分支）
- `leader_screen`：`candidates` 之后、`apply_hard_filters` 之前：`enrich_rows_from_db(db, candidates)`

- [ ] **Step 1: 接入代码**

示例（engine 普通配方）：

```python
    pool = ...
    total_scanned = len(pool)
    _maybe_enrich_industry(db, pool)
    rows = apply_hard_filters(pool, prefs)
```

条件选股每个 `apply_hard_filters` 前同理（含 moneyflow redis 分支、行情类末尾等）。

- [ ] **Step 2: 集成测**

```python
def test_recipe_enriches_empty_industry_before_filter() -> None:
    from unittest.mock import MagicMock, patch
    from app.schemas.screener import HardFilterPrefs, RecipeRunRequest
    from app.services.engine import run_recipe_screen
    from app.services.quotes import QuoteRow

    class _Store:
        def available(self):
            return True
        def meta(self):
            return {"quote_count": 1, "available": True}
        def load_ranked_quotes(self, field, *, pool=500):
            return [QuoteRow(symbol="SHSE.600519", name="茅台", change_pct=5.0, industry="")]

    with patch(
        "app.services.stock_industry.load_industry_map",
        return_value={"SHSE.600519": "白酒"},
    ):
        result = run_recipe_screen(
            RecipeRunRequest(
                recipe_id="intraday_multi",
                top_n=5,
                hard_filter=HardFilterPrefs(
                    min_amount_wan=0,
                    min_total_mv_yi=0,
                    allowed_industries="白酒",
                ),
            ),
            store=_Store(),  # type: ignore[arg-type]
            db=MagicMock(),
            user_id="u1",
        )
    assert result["row_count"] >= 1
    assert result["rows"][0]["industry"] == "白酒"
```

说明：若硬过滤「有 industry 且不在白名单才踢」，补全后应保留；未补全时空 industry 会通过过滤但结果 industry 仍空——本测断言补全后的行业字段。

可选 leader 测：mock `build_candidate_pool` + map，断言过滤后行带 industry。

- [ ] **Step 3: GREEN**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_stock_industry.py tests/test_engine.py tests/test_leader_screen.py -q
```

- [ ] **Step 4: Commit** — 跳过

---

### Task 3: gap / smoke + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap** — 选股备注：可补空行业；仍无行业下拉；「建议下一刀」另定

- [ ] **Step 2: smoke** — 同步行业映射后，Redis 缺行业时配方/龙头可见行业

- [ ] **Step 3: 全量 pytest**（前端无改可跳过 build，或快速 `npm run build`）

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest -q
```

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage

| Spec | Task |
|------|------|
| load + enrich + enrich_rows_from_db | 1 |
| condition / recipe / leader 挂载 | 2 |
| 非空不覆盖、db None 跳过 | 1–2 |
| gap / smoke | 3 |

## Placeholder scan

无 TBD。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-10-enrich-empty-industry.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）**  
2. **Inline Execution**  

Which approach?
