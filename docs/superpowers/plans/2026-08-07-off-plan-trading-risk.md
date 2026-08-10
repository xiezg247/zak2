# 计划外 + trading/risk 偏好 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 策略看盘标计划外；读写桌面同表 trading/risk 偏好；展示仓位占比。

**Architecture:** `off_plan` 纯函数 + `trading_risk` prefs（`auth.user_preferences`）+ 扩 `strategy_board`/`risk_summary` + 自选页卡片。

**Tech Stack:** FastAPI、SQLAlchemy text/ORM、现有 TradingPlan 模型、Vue WatchlistView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-off-plan-trading-risk-design.md`

## Global Constraints

- 只改 zak2；共用 PG，不改 zak 代码
- 无通知/下单/计划 CRUD
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/off_plan.py` | 当日 active 计划 vs 持仓 → off_plan 集合 |
| `backend/app/services/position_risk_tags.py` | TAG_ORDER 插入「计划外」；`off_plan: bool` 参数 |
| `backend/app/services/trading_risk.py` | prefs load/save/normalize + actual_pct |
| `backend/app/services/strategy_board.py` | 注入 off_plan、risk_summary |
| `backend/app/schemas/watchlist.py` | RiskSummary、TradingRiskOut/Put、行字段 |
| `backend/app/api/v1/watchlist.py` | GET/PUT trading-risk |
| `backend/tests/test_off_plan.py` / `test_trading_risk.py` / 扩展 board 测 |
| `frontend/src/api/watchlist.ts` / `WatchlistView.vue` | 卡片 + 计划外展示 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: off_plan + risk_tags「计划外」

**Files:**
- Create: `backend/app/services/off_plan.py`
- Modify: `backend/app/services/position_risk_tags.py`
- Create: `backend/tests/test_off_plan.py`
- Modify: `backend/tests/test_position_risk_tags.py`

**Interfaces:**
- `load_active_plan_vt_symbols(db, user_id, trade_date: str) -> set[str] | None`  
  - None = 无 active 计划；空 set = 有计划但无标的  
- `list_off_plan_vt_symbols(position_vts: list[str], plan_vts: set[str] | None) -> list[str]`  
  - `plan_vts is None` → `[]`  
- `compute_position_risk_tags(..., off_plan: bool = False)`  
- `TAG_ORDER` 含「计划外」在卖出信号之后

- [ ] **Step 1: 单测（失败先写）**

```python
# test_off_plan.py
from app.services.off_plan import list_off_plan_vt_symbols

def test_no_plan_means_none_off() -> None:
    assert list_off_plan_vt_symbols(["600519.SSE"], None) == []

def test_off_plan_diff() -> None:
    assert list_off_plan_vt_symbols(
        ["600519.SSE", "000001.SZSE"],
        {"600519.SSE"},
    ) == ["000001.SZSE"]
```

```python
# test_position_risk_tags.py 追加
def test_off_plan_tag_order() -> None:
    tags = compute_position_risk_tags(
        exit_signal="sell",
        unrealized_pnl_pct=-6,
        change_pct=None,
        volume_ratio=None,
        off_plan=True,
    )
    assert tags[:2] == ["卖出信号", "计划外"]
```

- [ ] **Step 2: 实现 off_plan + 更新 TAG_ORDER**

`load_active_plan_vt_symbols`：用 ORM `TradingPlan`/`TradingPlanSymbol` 或 text SQL：

```sql
SELECT id FROM trading_plans
WHERE user_id=:uid AND trade_date=:day AND status='active'
ORDER BY updated_at DESC LIMIT 1
```

再查 symbols → `to_vt_symbol`。

- [ ] **Step 3: pytest PASS**（相关文件）

- [ ] **Step 4: Commit** — 跳过

---

### Task 2: trading_risk prefs + API

**Files:**
- Create: `backend/app/services/trading_risk.py`
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/api/v1/watchlist.py`
- Create: `backend/tests/test_trading_risk.py`

**Interfaces:**
- `DEFAULT_STOP_LOSS_PCT = 0.05`, `DEFAULT_CAUTION_FLOAT_PCT = -5.0`
- `normalize_prefs(raw: dict) -> dict`
- `load_trading_risk_prefs(db, user_id) -> dict`
- `save_trading_risk_prefs(db, user_id, body: dict) -> dict`（校验失败 `ValueError` 中文）
- `compute_actual_position_pct(total_mv, total_capital) -> float | None`
- `normalize_plan_max_pct(raw: float) -> float | None`（>1 则 /100；≤0 → None）

Prefs SQL（与桌面同表）：

```sql
SELECT value_json FROM auth.user_preferences
WHERE user_id=:uid AND namespace='trading' AND key='risk'
```

Upsert：

```sql
INSERT INTO auth.user_preferences (user_id, namespace, key, value_json, updated_at)
VALUES (:uid, 'trading', 'risk', CAST(:v AS jsonb), NOW())
ON CONFLICT (user_id, namespace, key) DO UPDATE
SET value_json = EXCLUDED.value_json, updated_at = NOW()
```

（若 PK/唯一约束名不同，以现库为准；冲突则查 `\d auth.user_preferences`。）

Schemas：

```python
class TradingRiskPrefsOut(BaseModel):
    total_capital: float | None = None
    stop_loss_pct: float = 0.05
    caution_float_pct: float = -5.0
    realized_pnl_today: float | None = None

class TradingRiskPrefsPut(BaseModel):
    total_capital: float | None = None
    stop_loss_pct: float | None = None
    caution_float_pct: float | None = None
    realized_pnl_today: float | None = None
```

Routes：`GET/PUT /watchlist/trading-risk`。

- [ ] **Step 1–4: TDD normalize/save mock + API ValueError→400；Commit 跳过**

---

### Task 3: strategy_board 注入 + schema

**Files:**
- Modify: `backend/app/services/strategy_board.py`
- Modify: `backend/app/schemas/watchlist.py`（`StrategyPositionRow.off_plan`、`StrategyBoardOut.risk_summary`）
- Modify: `backend/app/services/position_risk_tags.py` 调用处 / `enrich_position_risk` 传 `off_plan`
- Modify: `backend/tests/test_strategy_board.py`

**risk_summary 组装：**

```python
prefs = load_trading_risk_prefs(db, user_id)
plan_vts = load_active_plan_vt_symbols(db, user_id, trade_date)
# trade_date: 用 bars.as_of 或 latest_open 字符串含横线
off_set = set(list_off_plan_vt_symbols([p["vt_symbol"] for p in positions], plan_vts))
for p in positions:
    op = p["vt_symbol"] in off_set
    p["off_plan"] = op
    # re-enrich tags with off_plan=op（或 enrich 时传入）
total_mv = sum(float(p["market_value"] or 0) for p in positions)
risk_summary = {
    "total_capital": prefs.get("total_capital"),
    "actual_position_pct": compute_actual_position_pct(total_mv, prefs.get("total_capital")),
    "plan_max_pct": normalize_plan_max_pct(active_plan.max_position_pct) if active else None,
    "off_plan_count": len(off_set),
    "off_plan_symbols": sorted(off_set),
    "active_plan_date": active_date or "",
}
```

`enrich_position_risk` 增加 `off_plan: bool = False` 并传给 `compute_position_risk_tags`。

- [ ] **单测：** enrich 含计划外；summary 字段存在（可 mock prefs/off_plan）
- [ ] **Commit** — 跳过

---

### Task 4: 前端 + 文档 + 全量

**Files:**
- `frontend/src/api/watchlist.ts` — types + `tradingRisk` GET/PUT
- `frontend/src/views/WatchlistView.vue` — 策略看盘上方 risk 卡片；持仓风险列已有 tags
- `docs/gap-vs-desktop.md` / `smoke-checklist.md`

**UI 卡片字段：**
- 总资金 number、止损%（可显示为百分数输入再 /100）、浮亏警戒
- 保存 → PUT → 刷新 board
- 展示：`actual_position_pct`、`off_plan_count`、`active_plan_date`

- [ ] **npm run build**
- [ ] **全量 pytest**
- [ ] **Commit** — 跳过

---

## Spec coverage

| Spec | Task |
|------|------|
| off_plan 算法 | 1 |
| risk_tags「计划外」 | 1+3 |
| trading/risk prefs API | 2 |
| risk_summary / board | 3 |
| 自选 UI + docs | 4 |

无 TBD。
