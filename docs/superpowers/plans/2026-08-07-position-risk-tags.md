# 策略看盘持仓风险 Tag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 策略看盘持仓行注入只读 `risk_tags`（浮亏/浮盈/急跌/大涨/放量/卖出信号）。

**Architecture:** 纯函数 `position_risk_tags` + `strategy_board` 组装时注入；前端持仓区增「风险」列；无新 API。

**Tech Stack:** FastAPI、现有 QuoteRow/strategy_board、Vue WatchlistView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-position-risk-tags-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 无 TickFlow、无通知、无计划外/开盘止损
- 阈值与排序按 spec 写死
- Commit 仅在用户明确要求时执行（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/position_risk_tags.py` | 纯函数 |
| `backend/tests/test_position_risk_tags.py` | 纯函数单测 |
| `backend/app/services/strategy_board.py` | 注入字段 |
| `backend/tests/test_strategy_board.py` | 断言 risk_tags |
| `frontend/src/api/watchlist.ts` | 类型 |
| `frontend/src/views/WatchlistView.vue` | 风险列 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: 纯函数 + 单测

**Files:**
- Create: `backend/app/services/position_risk_tags.py`
- Create: `backend/tests/test_position_risk_tags.py`

**Interfaces:**
- Produces:
  - `FLOAT_LOSS_PCT = -5.0`
  - `FLOAT_GAIN_PCT = 15.0`
  - `INTRADAY_DROP_PCT = -3.0`
  - `INTRADAY_SURGE_PCT = 5.0`
  - `VOLUME_RATIO_ACTIVE = 1.2`
  - `VOLUME_CHANGE_ABS_MIN = 1.5`
  - `TAG_ORDER: tuple[str, ...] = ("卖出信号", "急跌", "浮亏", "放量", "大涨", "浮盈")`
  - `compute_position_risk_tags(*, exit_signal, unrealized_pnl_pct, change_pct, volume_ratio) -> list[str]`
  - `primary_risk_tag(tags: list[str]) -> str`（空则 `""`）

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_position_risk_tags.py
from app.services.position_risk_tags import compute_position_risk_tags, primary_risk_tag


def test_sell_and_float_loss_order() -> None:
    tags = compute_position_risk_tags(
        exit_signal="sell",
        unrealized_pnl_pct=-6.0,
        change_pct=None,
        volume_ratio=None,
    )
    assert tags == ["卖出信号", "浮亏"]
    assert primary_risk_tag(tags) == "卖出信号"


def test_intraday_drop_surge_volume() -> None:
    tags = compute_position_risk_tags(
        exit_signal="na",
        unrealized_pnl_pct=None,
        change_pct=-3.0,
        volume_ratio=1.5,
    )
    assert "急跌" in tags
    assert "放量" in tags
    assert tags.index("急跌") < tags.index("放量")

    tags2 = compute_position_risk_tags(
        exit_signal=None,
        unrealized_pnl_pct=None,
        change_pct=5.0,
        volume_ratio=None,
    )
    assert tags2 == ["大涨"]


def test_float_gain() -> None:
    tags = compute_position_risk_tags(
        exit_signal="hold",
        unrealized_pnl_pct=15.0,
        change_pct=0.0,
        volume_ratio=1.0,
    )
    assert tags == ["浮盈"]


def test_missing_fields_empty() -> None:
    assert compute_position_risk_tags(
        exit_signal=None,
        unrealized_pnl_pct=None,
        change_pct=None,
        volume_ratio=None,
    ) == []
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_position_risk_tags.py -q
```

Expected: FAIL

- [ ] **Step 3: 实现**

```python
def compute_position_risk_tags(...):
    hit: set[str] = set()
    if (exit_signal or "").strip().lower() == "sell":
        hit.add("卖出信号")
    if change_pct is not None:
        cp = float(change_pct)
        if cp <= INTRADAY_DROP_PCT:
            hit.add("急跌")
        elif cp >= INTRADAY_SURGE_PCT:
            hit.add("大涨")
        if volume_ratio is not None and float(volume_ratio) >= VOLUME_RATIO_ACTIVE and abs(cp) >= VOLUME_CHANGE_ABS_MIN:
            hit.add("放量")
    if unrealized_pnl_pct is not None:
        pnl = float(unrealized_pnl_pct)
        if pnl <= FLOAT_LOSS_PCT:
            hit.add("浮亏")
        elif pnl >= FLOAT_GAIN_PCT:
            hit.add("浮盈")
    return [t for t in TAG_ORDER if t in hit]
```

- [ ] **Step 4: 跑测 PASS**

```bash
cd backend && uv run pytest tests/test_position_risk_tags.py -q
```

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: strategy_board 注入

**Files:**
- Modify: `backend/app/services/strategy_board.py`
- Modify: `backend/tests/test_strategy_board.py`

**Interfaces:**
- Consumes: `compute_position_risk_tags`, `primary_risk_tag`
- Produces: 持仓 dict 增加 `risk_tags: list[str]`、`risk_primary: str`

- [ ] **Step 1: 在持仓 `positions.append({...})` 前取 quote 的 change_pct / volume_ratio**

```python
from app.services.position_risk_tags import compute_position_risk_tags, primary_risk_tag

change_pct = float(getattr(q, "change_pct", 0) or 0) if q else None
# 无 quote 时 change_pct/volume_ratio 传 None
vr = float(getattr(q, "volume_ratio", 0) or 0) if q else None
if q is None:
    change_pct = None
    vr = None
tags = compute_position_risk_tags(
    exit_signal=exit_kind,
    unrealized_pnl_pct=pnl_pct,
    change_pct=change_pct,
    volume_ratio=vr,
)
# append:
"risk_tags": tags,
"risk_primary": primary_risk_tag(tags),
```

注意：`change_pct=0` 与「无行情」区分——无 `q` 才传 `None`；有 `q` 则传数值（含 0）。

- [ ] **Step 2: 单测** — 在现有 `test_strategy_board.py` 增加用例：mock 持仓 + quote 使 `pnl_pct≤-5` 或 `exit=sell`，断言 `risk_tags` 含对应项。（若现有测难改，新建 `tests/test_strategy_board_risk.py` 只测组装辅助或 patch `get_strategy_board` 依赖。）

最小可行：直接测纯函数已在 Task 1；本任务至少：

```python
def test_board_position_includes_risk_tags(monkeypatch):
    # 若 get_strategy_board 过重，可抽 _enrich_position_row 并测之
    ...
```

若抽函数成本高，则在 `get_strategy_board` 集成测中 mock SessionLocal/quotes 到能产出一行；否则 **允许** Task 2 仅改注入 + 用手工构造调用内部循环的轻量 helper：

```python
# strategy_board.py
def enrich_position_risk(row: dict, quote) -> dict:
    ...
    return row
```

并单测 `enrich_position_risk`。

**推荐实现：** 增加 `enrich_position_risk(row: dict[str, Any], *, change_pct, volume_ratio) -> dict`，在 append 前调用；单测该 helper。

- [ ] **Step 3: 跑测**

```bash
cd backend && uv run pytest tests/test_position_risk_tags.py tests/test_strategy_board.py -q
```

Expected: PASS（若新增文件一并跑）

- [ ] **Step 4: Commit** — 跳过

---

### Task 3: 前端 + 文档 + 全量验收

**Files:**
- Modify: `frontend/src/api/watchlist.ts` — `StrategyPositionRow` 加 `risk_tags?: string[]`、`risk_primary?: string`
- Modify: `frontend/src/views/WatchlistView.vue` — 表头「风险」列；`{{ row.risk_tags?.length ? row.risk_tags.join(' · ') : '—' }}`；`colspan` +1
- Modify: `docs/gap-vs-desktop.md`、`docs/smoke-checklist.md`

- [ ] **Step 1: TS + Vue**

持仓区 thead 在「退出」前或后加「风险」；空态 colspan 改为 8。

- [ ] **Step 2: gap**

- 总览「风控通知 / 交易链路」→ **薄**：策略看盘只读 risk tag；无通知/下单  
- 下一刀可写：计划外 / risk 偏好 / 通知历史  

- [ ] **Step 3: smoke**

自选策略看盘持仓区可见风险列（有浮亏/卖出信号时）

- [ ] **Step 4: 全量**

```bash
cd backend && uv run pytest -q
cd ../frontend && npm run build
```

Expected: 全绿

- [ ] **Step 5: Commit** — 跳过

---

## Spec coverage

| Spec | Task |
|------|------|
| 纯函数阈值/排序 | 1 |
| strategy_board 注入 | 2 |
| 前端风险列 | 3 |
| gap/smoke/验收 | 3 |

无 TBD。
