# 情绪+共振 → 次日计划草案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 雷达一键将情绪+用户加权共振 TopN 写入次日 `trading_plans` draft（可覆盖同日 draft，不改 active）。

**Architecture:** 新服务 `plan_draft` + `POST /api/v1/radar/plan-draft`；复用 `build_emotion_cycle` / `list_radar_resonance` / `TradingPlan` 表；Radar 按钮调用并提示跳转 Playbook。

**Tech Stack:** FastAPI、SQLAlchemy、`app.trade_calendar`、Vue RadarView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-resonance-plan-draft-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 只写 `status=draft`；绝不改 `active`
- 冰点/退潮 / 无卡 / 空共振 → 400 且不写库
- 无下单、无激活/编辑 UI、无 B（`sync_stock_industry`）
- Commit 仅用户明确要求时（默认跳过）
- 不打真网

**Clarifications（相对 spec 的显式落地）：**

- `trade_date` 入库格式：`YYYY-MM-DD`（与 `strategy_board._resolve_plan_trade_date` / 桌面一致）
- `max_position_pct`：`trading/risk` 偏好**无**仓位上限字段 → 本刀固定默认 `0.3`（可用模块常量 `DEFAULT_PLAN_MAX_POSITION_PCT`）
- `emotion_expected`：存 stage id（如 `divergence`），notes 里带 stage_label
- `plan_id`：`uuid.uuid4().hex`

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/plan_draft.py` | **新建** next trade date + upsert draft |
| `backend/app/schemas/market.py` | `PlanDraftRequest` / `PlanDraftOut` |
| `backend/app/api/v1/market.py` | `POST /radar/plan-draft` |
| `backend/tests/test_plan_draft.py` | **新建** 单测 |
| `frontend/src/api/market.ts` | `createPlanDraft` |
| `frontend/src/views/RadarView.vue` | 按钮 + 成功/失败文案 |
| `docs/gap-vs-desktop.md` / `docs/smoke-checklist.md` | 文档 |

---

### Task 1: `plan_draft` 服务 + 单测

**Files:**
- Create: `backend/app/services/plan_draft.py`
- Create: `backend/tests/test_plan_draft.py`

**Interfaces:**
- `DEFAULT_PLAN_MAX_POSITION_PCT = 0.3`
- `clamp_top_n(n: int | None) -> int` — 默认 5，夹逼 3–8
- `normalize_trade_date(raw: str | None) -> str | None` — 接受 `YYYYMMDD` / `YYYY-MM-DD` → `YYYY-MM-DD`；非法 → None
- `resolve_next_trade_date(db: Session, *, today: date | None = None) -> tuple[str, bool]`  
  - 返回 `(YYYY-MM-DD, used_calendar_fallback)`  
  - SQL：`SELECT cal_date FROM app.trade_calendar WHERE is_open = 1 AND cal_date > :today ORDER BY cal_date ASC LIMIT 1`（`today` 用 `YYYY-MM-DD`；若库内存 `YYYYMMDD`，用 `REPLACE(cal_date,'-','') > :ymd` 双兼容，见实现注）  
  - 无行：`latest_open_yyyymmdd(db)` → 格式化为 `YYYY-MM-DD`，`used_calendar_fallback=True`
- `create_resonance_plan_draft(db, user_id, *, top_n: int | None = None, trade_date: str | None = None) -> dict`

`create_resonance_plan_draft` 行为按 spec；`replaced` 表示覆盖了已有 draft。

日历日期兼容实现注：查询时优先

```sql
SELECT cal_date FROM app.trade_calendar
WHERE is_open = 1
  AND REPLACE(cal_date, '-', '') > :ymd
ORDER BY REPLACE(cal_date, '-', '') ASC
LIMIT 1
```

再把结果 normalize 成 `YYYY-MM-DD`。

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_plan_draft.py
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.content import TradingPlan, TradingPlanSymbol
from app.schemas.market import RadarResonanceEntry, RadarResonanceOut
from app.services import plan_draft as pd


def test_clamp_top_n() -> None:
    assert pd.clamp_top_n(None) == 5
    assert pd.clamp_top_n(2) == 3
    assert pd.clamp_top_n(9) == 8
    assert pd.clamp_top_n(5) == 5


def test_normalize_trade_date() -> None:
    assert pd.normalize_trade_date("20260811") == "2026-08-11"
    assert pd.normalize_trade_date("2026-08-11") == "2026-08-11"
    assert pd.normalize_trade_date("bad") is None


def test_ice_stage_raises_no_write() -> None:
    db = MagicMock()
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "ice", "stage_label": "冰点"}),
        patch("app.services.plan_draft.list_radar_cards") as cards,
    ):
        with pytest.raises(HTTPException) as ei:
            pd.create_resonance_plan_draft(db, "u1")
        assert ei.value.status_code == 400
        assert "不宜新开" in str(ei.value.detail)
        cards.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()


def test_no_cards_400() -> None:
    db = MagicMock()
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[]),
    ):
        with pytest.raises(HTTPException) as ei:
            pd.create_resonance_plan_draft(db, "u1")
        assert ei.value.status_code == 400
        assert "雷达卡片" in str(ei.value.detail)


def test_empty_resonance_400() -> None:
    db = MagicMock()
    empty = RadarResonanceOut(min_cards=2, top_n=5, total=0, entries=[])
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=empty),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
    ):
        with pytest.raises(HTTPException) as ei:
            pd.create_resonance_plan_draft(db, "u1", top_n=5)
        assert "共振" in str(ei.value.detail)


def test_create_draft_and_replace() -> None:
    db = MagicMock()
    entries = [
        RadarResonanceEntry(
            vt_symbol="600519.SSE",
            name="茅台",
            card_count=2,
            card_titles=["选股·龙头", "发现·连板梯队"],
            resonance_score=2.9,
            change_pct=2.0,
            last_price=1800.0,
        )
    ]
    out = RadarResonanceOut(min_cards=2, top_n=5, total=1, entries=entries)

    # first call: no existing draft
    db.scalar.return_value = None
    db.scalars.return_value = []

    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=out),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
        patch("app.services.plan_draft.uuid") as u,
    ):
        u.uuid4.return_value.hex = "abc123"
        result = pd.create_resonance_plan_draft(db, "u1", top_n=5)

    assert result["status"] == "draft"
    assert result["trade_date"] == "2026-08-11"
    assert result["replaced"] is False
    assert result["symbol_count"] == 1
    assert result["symbols"][0]["vt_symbol"] == "600519.SSE"
    assert result["emotion_expected"] == "divergence"
    assert db.add.called
    assert db.commit.called

    # second call: existing draft → replaced
    existing = MagicMock(spec=TradingPlan)
    existing.id = "oldplan"
    existing.status = "draft"
    db.scalar.return_value = existing
    db.scalars.return_value = [MagicMock(spec=TradingPlanSymbol)]

    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=out),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
    ):
        result2 = pd.create_resonance_plan_draft(db, "u1", top_n=5)

    assert result2["replaced"] is True
    assert result2["plan_id"] == "oldplan"
    db.delete.assert_called()  # symbols cleared


def test_does_not_touch_active() -> None:
    """查 draft 的 where 必须含 status==draft；active 不应被 scalar 命中。"""
    # 实现后用 inspect 或行为测：mock scalar 只在 draft 查询时返回 None；
    # 另起 active MagicMock 不应被 delete/update。
    db = MagicMock()
    db.scalar.return_value = None
    entries = [
        RadarResonanceEntry(
            vt_symbol="600519.SSE",
            name="茅台",
            card_count=2,
            card_titles=["A"],
            resonance_score=1.0,
        )
    ]
    out = RadarResonanceOut(min_cards=2, top_n=5, total=1, entries=entries)
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "startup", "stage_label": "启动"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=out),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
        patch("app.services.plan_draft.uuid") as u,
    ):
        u.uuid4.return_value.hex = "new1"
        pd.create_resonance_plan_draft(db, "u1")
    # 新建的 TradingPlan.status 必须是 draft
    added = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], TradingPlan)]
    assert added
    assert all(p.status == "draft" for p in added)
```

- [ ] **Step 2: RED**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_plan_draft.py -q
```

Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `plan_draft.py`**

骨架要点：

```python
DEFAULT_PLAN_MAX_POSITION_PCT = 0.3

def create_resonance_plan_draft(...):
    cycle = build_emotion_cycle(db)
    stage = str(cycle.get("stage") or "")
    if stage in {"ice", "recession"}:
        raise HTTPException(400, detail="当前情绪不宜新开（冰点/退潮）")
    ...
    # upsert draft
    existing = db.scalar(
        select(TradingPlan).where(
            TradingPlan.user_id == user_id,
            TradingPlan.trade_date == td,
            TradingPlan.status == "draft",
        ).order_by(desc(TradingPlan.updated_at)).limit(1)
    )
    replaced = existing is not None
    if existing:
        # delete symbols for existing.id; update meta fields
        plan = existing
    else:
        plan = TradingPlan(id=uuid.uuid4().hex, user_id=user_id, trade_date=td, status="draft", ...)
        db.add(plan)
    # add TradingPlanSymbol rows via parse_flexible_symbol
    db.commit()
    return {...}
```

`now` 字段：与 `feed.py` / 桌面一致用 ISO UTC 字符串（可 `datetime.now(timezone.utc).replace(microsecond=0).isoformat()`）。

- [ ] **Step 4: GREEN**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_plan_draft.py -q
```

Expected: PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: API + Radar UI

**Files:**
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/app/api/v1/market.py`
- Modify: `frontend/src/api/market.ts`
- Modify: `frontend/src/views/RadarView.vue`
- Modify: `backend/tests/test_plan_draft.py`（可选：API 级 1 测，用 TestClient + patch service）

**Interfaces:**
- Schema:
  - `PlanDraftRequest`: `top_n: int | None = None`, `trade_date: str | None = None`
  - `PlanDraftOut`: `plan_id, trade_date, status, emotion_expected, symbol_count, symbols: list[PlanDraftSymbol], replaced`
  - `PlanDraftSymbol`: `vt_symbol: str`, `name: str = ""`
- Route: `POST /radar/plan-draft` → `plan_draft.create_resonance_plan_draft(db, str(user.id), top_n=body.top_n, trade_date=body.trade_date)`
- FE: `marketApi.createPlanDraft(body?)` → POST JSON
- Radar: 按钮「生成次日计划草案」；`draftBusy` / `draftMsg`；成功含 router-link 或 `<a>` 到 `/playbook`

- [ ] **Step 1: Schema + route**

在 `market.py` 靠近 resonance 路由处增加 POST；import schemas + `plan_draft`。

- [ ] **Step 2: 可选 API 测**

```python
def test_api_plan_draft_ok(client_with_user):  # 沿用项目现有 TestClient fixture 模式
    ...
```

若项目无统一 fixture，可仿 `test_radar_resonance_weights.py` / `test_emotion_thresholds_api.py` 的 client 写法；**至少保证 Task1 服务测已覆盖**，API 测建议有一条 200 + 一条 400。

- [ ] **Step 3: Frontend**

`market.ts`：

```ts
export type PlanDraftOut = {
  plan_id: string
  trade_date: string
  status: string
  emotion_expected: string
  symbol_count: number
  symbols: { vt_symbol: string; name?: string }[]
  replaced: boolean
}

// in marketApi:
createPlanDraft: (body: { top_n?: number; trade_date?: string } = {}) =>
  api<PlanDraftOut>('/api/v1/radar/plan-draft', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
```

`RadarView.vue`：工具栏增加按钮（可用 `primary` 或 `ghost`，与「共振选股」并列）；成功文案示例：

`已写入 draft · ${r.trade_date} · ${r.symbol_count} 只${r.replaced ? '（已覆盖）' : ''}`

附「去守则看计划」→ `router.push('/playbook')` 或 `<RouterLink>`。

- [ ] **Step 4: build**

```bash
cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build
```

Expected: 成功

- [ ] **Step 5: Commit** — 跳过

---

### Task 3: gap / smoke + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap**

总览「市场 / 板块 / 雷达」备注追加：可生成次日 draft；仍无激活/编辑。

「建议下一刀」改为：`sync_stock_industry` Web 可跑（B）。

- [ ] **Step 2: smoke**

§5 追加：

- `/radar`「生成次日计划草案」可写 draft；Playbook 可见  
- 冰点/退潮或无共振时失败文案明确  
- 同日再点覆盖 draft  

- [ ] **Step 3: 全量 pytest**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest -q
```

Expected: 全绿（基线约 286+）

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage（自检）

| Spec | Task |
|------|------|
| POST plan-draft + upsert draft | 1–2 |
| 冰点/无卡/空共振 400 | 1 |
| 下一交易日 + fallback | 1 |
| max_position 默认 0.3 | 1（clarification） |
| Radar 按钮 + Playbook 链接 | 2 |
| gap/smoke；B 另刀 | 3 |
| pytest + build | 2–3 |

## Placeholder scan

无 TBD。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-10-resonance-plan-draft.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每任务新子代理 + 任务间复审  
2. **Inline Execution** — 本会话连续执行  

Which approach?
