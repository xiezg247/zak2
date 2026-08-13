# 交易计划生命周期闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 守则完成交易计划激活/废弃/轻编辑，打通自选「计划外」对 active 的依赖。

**Architecture:** 新建 `plan_manage.py` 承载状态机与 PATCH；从 `feed.list_plans` 抽出 `plan_to_out`；API 挂 `content.py`；`PlaybookView` 就地操作。不改 `off_plan` / `plan_draft` 覆盖 draft 语义。

**Tech Stack:** FastAPI · SQLAlchemy · Pydantic · Vue 3 · pytest · TestClient

**Spec:** `docs/superpowers/specs/2026-08-13-trading-plan-lifecycle-design.md`

## Global Constraints

- 状态字仅：`draft` | `active` | `abandoned`
- 激活同日替换：旧 active → abandoned
- PATCH：`symbols` 省略=不改；出现=整表替换（空数组清空）；上限 20
- `max_position_pct` 存 0–1；`>1` 则 `/100`；非法 ≤0 → 400
- `abandoned` 不可 PATCH（403）；可激活回 active
- 不改自选页、不新建 `/plans`、不下单
- Commit 简体中文；不 push

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/schemas/content.py` | `PlanUpdate` |
| `backend/app/services/feed.py` | 抽出 `plan_to_out`；`list_plans` 复用 |
| `backend/app/services/plan_manage.py` | `get_user_plan` / `update_plan` / `activate_plan` / `abandon_plan` |
| `backend/app/api/v1/content.py` | PATCH + activate + abandon 路由 |
| `backend/tests/test_plan_manage.py` | 服务与 API 测 |
| `frontend/src/api/content.ts` | `patchPlan` / `activatePlan` / `abandonPlan` |
| `frontend/src/views/PlaybookView.vue` | 计划区交互 |
| `docs/product-roadmap.md` / `docs/smoke-checklist.md` | 文档 |

---

### Task 1: PlanUpdate schema + plan_to_out

**Files:**
- Modify: `backend/app/schemas/content.py`
- Modify: `backend/app/services/feed.py`
- Test: `backend/tests/test_plan_manage.py`（本 task 先建 `test_plan_to_out`）

**Interfaces:**
- Produces: `PlanUpdate`；`feed.plan_to_out(plan, symbols_rows) -> PlanOut`

- [ ] **Step 1: 写失败测**

创建 `backend/tests/test_plan_manage.py`：

```python
from __future__ import annotations

from unittest.mock import MagicMock

from app.schemas.content import PlanOut
from app.services import feed as feed_svc


def test_plan_to_out_maps_symbols() -> None:
    plan = MagicMock()
    plan.id = "p1"
    plan.trade_date = "2026-08-14"
    plan.emotion_expected = "divergence"
    plan.max_position_pct = 0.3
    plan.notes = "n"
    plan.status = "draft"
    sym = MagicMock()
    sym.symbol = "600519"
    sym.exchange = "SSE"
    sym.allowed_modes = ""
    sym.entry_conditions = "e"
    sym.exit_conditions = ""
    out = feed_svc.plan_to_out(plan, [sym])
    assert isinstance(out, PlanOut)
    assert out.id == "p1"
    assert out.status == "draft"
    assert out.symbols[0]["vt_symbol"] == "600519.SSE"
```

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && uv run pytest tests/test_plan_manage.py::test_plan_to_out_maps_symbols -v`  
Expected: FAIL（`plan_to_out` 不存在）

- [ ] **Step 3: schema + 实现 plan_to_out**

在 `content.py` `PlanOut` 后加：

```python
class PlanUpdate(BaseModel):
    notes: str | None = None
    max_position_pct: float | None = None
    symbols: list[str] | None = None
```

在 `feed.py` 抽出（供 `list_plans` 与 `plan_manage` 用）：

```python
def plan_to_out(plan: TradingPlan, symbols: list[TradingPlanSymbol]) -> PlanOut:
    return PlanOut(
        id=plan.id,
        trade_date=plan.trade_date,
        emotion_expected=plan.emotion_expected or "",
        max_position_pct=float(plan.max_position_pct or 0),
        notes=plan.notes or "",
        status=plan.status,
        symbols=[
            {
                "symbol": s.symbol,
                "exchange": s.exchange,
                "vt_symbol": to_vt_symbol(s.symbol, s.exchange),
                "allowed_modes": s.allowed_modes,
                "entry_conditions": s.entry_conditions,
                "exit_conditions": s.exit_conditions,
            }
            for s in symbols
        ],
    )
```

`list_plans` 循环内改为 `out.append(plan_to_out(p, syms))`。

- [ ] **Step 4: 跑测通过**

Run: `cd backend && uv run pytest tests/test_plan_manage.py::test_plan_to_out_maps_symbols -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/content.py backend/app/services/feed.py backend/tests/test_plan_manage.py
git commit -m "$(cat <<'EOF'
refactor(plans): 抽出 plan_to_out 并增加 PlanUpdate

供计划生命周期 API 复用列表组装逻辑。
EOF
)"
```

---

### Task 2: activate_plan / abandon_plan

**Files:**
- Create: `backend/app/services/plan_manage.py`
- Modify: `backend/tests/test_plan_manage.py`

**Interfaces:**
- Consumes: `feed.plan_to_out`
- Produces:
  - `get_user_plan(db, user_id, plan_id) -> TradingPlan`（缺失 404）
  - `load_plan_out(db, user_id, plan) -> PlanOut`
  - `activate_plan(db, user_id, plan_id) -> PlanOut`
  - `abandon_plan(db, user_id, plan_id) -> PlanOut`

- [ ] **Step 1: 写失败测（激活替换 + 废弃幂等）**

追加到 `test_plan_manage.py`：

```python
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.content import TradingPlan
from app.services import plan_manage as pm


def _plan(**kw):
    p = MagicMock(spec=TradingPlan)
    p.id = kw.get("id", "p1")
    p.user_id = kw.get("user_id", "u1")
    p.trade_date = kw.get("trade_date", "2026-08-14")
    p.status = kw.get("status", "draft")
    p.emotion_expected = ""
    p.max_position_pct = 0.3
    p.notes = ""
    p.updated_at = "t0"
    return p


def test_activate_replaces_same_day_active() -> None:
    draft = _plan(id="d1", status="draft")
    old = _plan(id="a1", status="active")
    db = MagicMock()
    # get_user_plan → draft；再查同日 active → [old]
    db.scalar.side_effect = [draft]
    db.scalars.return_value = iter([old])
    with (
        patch("app.services.plan_manage._now", return_value="t1"),
        patch("app.services.plan_manage.load_plan_out", return_value=MagicMock(status="active", id="d1")) as load,
    ):
        out = pm.activate_plan(db, "u1", "d1")
    assert old.status == "abandoned"
    assert draft.status == "active"
    assert draft.updated_at == "t1"
    db.commit.assert_called()
    assert out.id == "d1"


def test_abandon_idempotent() -> None:
    abandoned = _plan(status="abandoned")
    db = MagicMock()
    db.scalar.return_value = abandoned
    with patch(
        "app.services.plan_manage.load_plan_out",
        return_value=MagicMock(status="abandoned", id="p1"),
    ):
        out = pm.abandon_plan(db, "u1", "p1")
    assert abandoned.status == "abandoned"
    db.commit.assert_called()
    assert out.status == "abandoned"


def test_activate_missing_404() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as ei:
        pm.activate_plan(db, "u1", "missing")
    assert ei.value.status_code == 404
```

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && uv run pytest tests/test_plan_manage.py::test_activate_replaces_same_day_active tests/test_plan_manage.py::test_abandon_idempotent tests/test_plan_manage.py::test_activate_missing_404 -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 plan_manage 状态机**

创建 `backend/app/services/plan_manage.py`：

```python
"""交易计划激活 / 废弃 / 轻编辑。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.content import TradingPlan, TradingPlanSymbol
from app.schemas.content import PlanOut
from app.services.feed import plan_to_out
from app.services.symbols import parse_flexible_symbol, to_vt_symbol
from app.services.trading_risk import normalize_plan_max_pct

MAX_PLAN_SYMBOLS = 20


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def get_user_plan(db: Session, user_id: str, plan_id: str) -> TradingPlan:
    plan = db.scalar(
        select(TradingPlan).where(TradingPlan.id == plan_id, TradingPlan.user_id == user_id)
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan


def load_plan_out(db: Session, user_id: str, plan: TradingPlan) -> PlanOut:
    syms = list(
        db.scalars(
            select(TradingPlanSymbol)
            .where(TradingPlanSymbol.plan_id == plan.id, TradingPlanSymbol.user_id == user_id)
            .order_by(TradingPlanSymbol.sort_order)
        )
    )
    return plan_to_out(plan, syms)


def activate_plan(db: Session, user_id: str, plan_id: str) -> PlanOut:
    plan = get_user_plan(db, user_id, plan_id)
    if plan.status == "active":
        return load_plan_out(db, user_id, plan)
    if plan.status not in {"draft", "abandoned"}:
        raise HTTPException(status_code=400, detail=f"无法激活状态「{plan.status}」")
    now = _now()
    others = list(
        db.scalars(
            select(TradingPlan).where(
                TradingPlan.user_id == user_id,
                TradingPlan.trade_date == plan.trade_date,
                TradingPlan.status == "active",
                TradingPlan.id != plan.id,
            )
        )
    )
    for o in others:
        o.status = "abandoned"
        o.updated_at = now
    plan.status = "active"
    plan.updated_at = now
    db.commit()
    db.refresh(plan)
    return load_plan_out(db, user_id, plan)


def abandon_plan(db: Session, user_id: str, plan_id: str) -> PlanOut:
    plan = get_user_plan(db, user_id, plan_id)
    if plan.status != "abandoned":
        plan.status = "abandoned"
        plan.updated_at = _now()
        db.commit()
        db.refresh(plan)
    return load_plan_out(db, user_id, plan)
```

（`update_plan` 留到 Task 3；本文件可先不写 symbols 替换，或预留占位——**本 task 只实现到 abandon**。）

注意：MagicMock 测里 `db.scalars(...).` 对 activate 的「查 others」用 `scalars`；`get_user_plan` 用 `scalar`。实现与测的 side_effect 对齐：若 `activate` 内对 others 用 `db.scalars(select...)`，测中 `db.scalars.return_value = MagicMock` 且 `__iter__` / `all`——更稳写法：

实现里：

```python
others = list(db.scalars(select(...)))
```

测里：

```python
db.scalars.return_value = [old]  # 若 list() 直接迭代失败，改为：
# mock_scalars = MagicMock()
# mock_scalars.__iter__ = lambda self: iter([old])
# db.scalars.return_value = mock_scalars
```

或用 `db.execute` 模式——以跑通为准，允许微调 mock。

- [ ] **Step 4: 跑测通过**

Run: `cd backend && uv run pytest tests/test_plan_manage.py -v -k "activate or abandon"`  
Expected: PASS（含 Task 1）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan_manage.py backend/tests/test_plan_manage.py
git commit -m "$(cat <<'EOF'
feat(plans): 实现计划激活与废弃状态机

同日激活替换旧 active；废弃幂等。
EOF
)"
```

---

### Task 3: update_plan（轻编辑）

**Files:**
- Modify: `backend/app/services/plan_manage.py`
- Modify: `backend/tests/test_plan_manage.py`

**Interfaces:**
- Produces: `update_plan(db, user_id, plan_id, *, notes=None, max_position_pct=None, symbols=None) -> PlanOut`
- `symbols is None` → 不改标的；`list` → 整表替换

- [ ] **Step 1: 写失败测**

```python
def test_update_rejects_abandoned() -> None:
    plan = _plan(status="abandoned")
    db = MagicMock()
    db.scalar.return_value = plan
    with pytest.raises(HTTPException) as ei:
        pm.update_plan(db, "u1", "p1", notes="x")
    assert ei.value.status_code == 403


def test_update_symbols_replace() -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    with (
        patch("app.services.plan_manage._now", return_value="t2"),
        patch(
            "app.services.plan_manage.load_plan_out",
            return_value=MagicMock(id="p1", notes="hi"),
        ),
    ):
        pm.update_plan(db, "u1", "p1", notes="hi", symbols=["600519.SSE", "000001.SZSE"])
    assert plan.notes == "hi"
    db.execute.assert_called()  # delete symbols
    assert db.add.call_count == 2
    db.commit.assert_called()


def test_update_max_pct_percent_form() -> None:
    plan = _plan(status="active")
    db = MagicMock()
    db.scalar.return_value = plan
    with patch(
        "app.services.plan_manage.load_plan_out",
        return_value=MagicMock(id="p1"),
    ):
        pm.update_plan(db, "u1", "p1", max_position_pct=30)
    assert abs(plan.max_position_pct - 0.3) < 1e-9
```

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && uv run pytest tests/test_plan_manage.py::test_update_rejects_abandoned tests/test_plan_manage.py::test_update_symbols_replace tests/test_plan_manage.py::test_update_max_pct_percent_form -v`  
Expected: FAIL

- [ ] **Step 3: 实现 update_plan**

追加到 `plan_manage.py`：

```python
def _normalize_max_pct(raw: float) -> float:
    n = normalize_plan_max_pct(float(raw))
    if n is None or n <= 0 or n > 1:
        raise HTTPException(status_code=400, detail="仓位上限须在 (0, 100%]（或 0–1 小数）")
    return n


def _replace_symbols(db: Session, user_id: str, plan: TradingPlan, raw_list: list[str]) -> None:
    if len(raw_list) > MAX_PLAN_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"标的最多 {MAX_PLAN_SYMBOLS} 只")
    parsed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in raw_list:
        try:
            code, exch = parse_flexible_symbol(raw)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        vt = to_vt_symbol(code, exch)
        if vt in seen:
            continue
        seen.add(vt)
        parsed.append((code, exch))
    db.execute(
        delete(TradingPlanSymbol).where(
            TradingPlanSymbol.plan_id == plan.id,
            TradingPlanSymbol.user_id == user_id,
        )
    )
    for i, (code, exch) in enumerate(parsed):
        db.add(
            TradingPlanSymbol(
                plan_id=plan.id,
                symbol=code,
                exchange=exch,
                user_id=user_id,
                allowed_modes="",
                entry_conditions="",
                exit_conditions="",
                sort_order=i,
            )
        )


def update_plan(
    db: Session,
    user_id: str,
    plan_id: str,
    *,
    notes: str | None = None,
    max_position_pct: float | None = None,
    symbols: list[str] | None = None,
) -> PlanOut:
    plan = get_user_plan(db, user_id, plan_id)
    if plan.status == "abandoned":
        raise HTTPException(status_code=403, detail="已废弃计划不可编辑")
    if notes is None and max_position_pct is None and symbols is None:
        raise HTTPException(status_code=400, detail="请至少提供 notes / max_position_pct / symbols 之一")
    if notes is not None:
        plan.notes = notes
    if max_position_pct is not None:
        plan.max_position_pct = _normalize_max_pct(max_position_pct)
    if symbols is not None:
        _replace_symbols(db, user_id, plan, symbols)
    plan.updated_at = _now()
    db.commit()
    db.refresh(plan)
    return load_plan_out(db, user_id, plan)
```

按测调整：`delete` 若用 `db.execute(delete(...))`，assert `db.execute`；若用 `db.delete` 则改测。

- [ ] **Step 4: 跑测通过**

Run: `cd backend && uv run pytest tests/test_plan_manage.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan_manage.py backend/tests/test_plan_manage.py
git commit -m "$(cat <<'EOF'
feat(plans): 支持计划轻编辑 notes/仓位/标的

abandoned 禁止编辑；symbols 省略与整表替换语义分离。
EOF
)"
```

---

### Task 4: HTTP 路由

**Files:**
- Modify: `backend/app/api/v1/content.py`
- Modify: `backend/tests/test_plan_manage.py`

**Interfaces:**
- `PATCH /api/v1/playbook/plans/{plan_id}`
- `POST /api/v1/playbook/plans/{plan_id}/activate`
- `POST /api/v1/playbook/plans/{plan_id}/abandon`

- [ ] **Step 1: API 测（mock service）**

```python
from uuid import uuid4
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User
from app.schemas.content import PlanOut


def _user() -> User:
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("x"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _client() -> TestClient:
    app = create_app()
    u = _user()

    def override_db():
        yield MagicMock()

    def override_user():
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app), u


def test_api_activate_ok() -> None:
    client, u = _client()
    fake = PlanOut(
        id="p1",
        trade_date="2026-08-14",
        emotion_expected="",
        max_position_pct=0.3,
        notes="",
        status="active",
        symbols=[],
    )
    with patch("app.api.v1.content.plan_manage_svc.activate_plan", return_value=fake) as act:
        r = client.post("/api/v1/playbook/plans/p1/activate")
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    act.assert_called_once()
    assert act.call_args.args[1] == str(u.id)


def test_api_patch_ok() -> None:
    client, u = _client()
    fake = PlanOut(
        id="p1",
        trade_date="2026-08-14",
        emotion_expected="",
        max_position_pct=0.25,
        notes="x",
        status="draft",
        symbols=[],
    )
    with patch("app.api.v1.content.plan_manage_svc.update_plan", return_value=fake) as upd:
        r = client.patch("/api/v1/playbook/plans/p1", json={"notes": "x", "max_position_pct": 0.25})
    assert r.status_code == 200
    assert r.json()["notes"] == "x"
    upd.assert_called_once()
```

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && uv run pytest tests/test_plan_manage.py::test_api_activate_ok tests/test_plan_manage.py::test_api_patch_ok -v`  
Expected: FAIL（404 路由）

- [ ] **Step 3: 挂路由**

`content.py`：

```python
from app.schemas.content import PlanUpdate  # 加入既有 import
from app.services import plan_manage as plan_manage_svc

@router.patch("/playbook/plans/{plan_id}", response_model=PlanOut)
def patch_plan(
    plan_id: str,
    body: PlanUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    return plan_manage_svc.update_plan(
        db,
        str(user.id),
        plan_id,
        notes=body.notes,
        max_position_pct=body.max_position_pct,
        symbols=body.symbols,
    )


@router.post("/playbook/plans/{plan_id}/activate", response_model=PlanOut)
def post_activate_plan(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    return plan_manage_svc.activate_plan(db, str(user.id), plan_id)


@router.post("/playbook/plans/{plan_id}/abandon", response_model=PlanOut)
def post_abandon_plan(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    return plan_manage_svc.abandon_plan(db, str(user.id), plan_id)
```

放在现有 `get_plans` 之后。

- [ ] **Step 4: 跑测通过**

Run: `cd backend && uv run pytest tests/test_plan_manage.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/content.py backend/tests/test_plan_manage.py
git commit -m "$(cat <<'EOF'
feat(api): 暴露计划激活/废弃/轻编辑接口

守则页可调用 playbook plans 写路径。
EOF
)"
```

---

### Task 5: Playbook 前端

**Files:**
- Modify: `frontend/src/api/content.ts`
- Modify: `frontend/src/views/PlaybookView.vue`

**Interfaces:**
- Consumes: 上述三 API
- Produces: 主列表 draft+active；历史折叠 abandoned；编辑/激活/废弃

- [ ] **Step 1: contentApi**

扩展 `Plan` symbols 类型（含可选 `symbol`/`exchange`）并加：

```typescript
  patchPlan: (id: string, body: { notes?: string; max_position_pct?: number; symbols?: string[] }) =>
    api<Plan>(`/api/v1/playbook/plans/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  activatePlan: (id: string) =>
    api<Plan>(`/api/v1/playbook/plans/${encodeURIComponent(id)}/activate`, { method: 'POST' }),
  abandonPlan: (id: string) =>
    api<Plan>(`/api/v1/playbook/plans/${encodeURIComponent(id)}/abandon`, { method: 'POST' }),
```

- [ ] **Step 2: PlaybookView 状态与动作**

在 script 增加（保留原 sections/discipline）：

```typescript
import { computed, onMounted, ref } from 'vue'
// ...
const msg = ref('')
const historyOpen = ref(false)
const editingId = ref('')
const editNotes = ref('')
const editMaxPct = ref(30)
const editSymbols = ref<string[]>([])
const symbolDraft = ref('')
const acting = ref(false)

const livePlans = computed(() => plans.value.filter((p) => p.status !== 'abandoned'))
const historyPlans = computed(() => plans.value.filter((p) => p.status === 'abandoned'))

function upsertPlan(p: Plan) {
  const i = plans.value.findIndex((x) => x.id === p.id)
  if (i >= 0) plans.value[i] = p
  else plans.value = [p, ...plans.value]
  // 同日替换后刷新列表更稳：
}

async function reloadPlans() {
  plans.value = await contentApi.plans()
}

function startEdit(p: Plan) {
  editingId.value = p.id
  editNotes.value = p.notes || ''
  editMaxPct.value = Math.round((p.max_position_pct || 0) * 100)
  editSymbols.value = p.symbols.map((s) => s.vt_symbol)
  symbolDraft.value = ''
  msg.value = ''
}

function cancelEdit() {
  editingId.value = ''
}

function addSymbol() {
  const t = symbolDraft.value.trim()
  if (!t) return
  if (editSymbols.value.length >= 20) {
    error.value = '标的最多 20 只'
    return
  }
  if (!editSymbols.value.includes(t)) editSymbols.value = [...editSymbols.value, t]
  symbolDraft.value = ''
}

function removeSymbol(vt: string) {
  editSymbols.value = editSymbols.value.filter((x) => x !== vt)
}

async function saveEdit(id: string) {
  acting.value = true
  error.value = ''
  msg.value = ''
  try {
    const p = await contentApi.patchPlan(id, {
      notes: editNotes.value,
      max_position_pct: editMaxPct.value / 100,
      symbols: [...editSymbols.value],
    })
    await reloadPlans()
    editingId.value = ''
    msg.value = '已保存'
    void p
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    acting.value = false
  }
}

async function activate(id: string) {
  acting.value = true
  error.value = ''
  msg.value = ''
  try {
    await contentApi.activatePlan(id)
    await reloadPlans()
    msg.value = '已激活，回自选可看计划外'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '激活失败'
  } finally {
    acting.value = false
  }
}

async function abandon(id: string) {
  if (!confirm('确认废弃该计划？')) return
  acting.value = true
  error.value = ''
  msg.value = ''
  try {
    await contentApi.abandonPlan(id)
    await reloadPlans()
    msg.value = '已废弃'
    if (editingId.value === id) editingId.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '废弃失败'
  } finally {
    acting.value = false
  }
}
```

- [ ] **Step 3: 模板替换计划区**

将原 `section.plans` 替换为（样式复用 `.chip` / `.ghost` / `.primary`，可加 `.plan.active` 边框与 `.badge`）：

```vue
      <p v-if="msg" class="ok">{{ msg }}</p>

      <section class="plans" v-if="livePlans.length || historyPlans.length">
        <h2>交易计划</h2>
        <div
          class="plan"
          v-for="p in livePlans"
          :key="p.id"
          :class="{ active: p.status === 'active' }"
        >
          <div class="plan-head">
            <strong>{{ p.trade_date }}</strong>
            <span class="badge" :data-status="p.status">{{ p.status }}</span>
            <span class="muted">仓位上限 {{ (p.max_position_pct * 100).toFixed(0) }}%</span>
            <span v-if="p.status === 'active'" class="tip">自选计划外以此为准</span>
          </div>

          <template v-if="editingId === p.id">
            <label class="field">
              仓位上限 %
              <input type="number" v-model.number="editMaxPct" min="1" max="100" step="1" />
            </label>
            <label class="field">
              备注
              <input type="text" v-model="editNotes" />
            </label>
            <div class="syms">
              <span v-for="vt in editSymbols" :key="vt" class="chip">
                {{ vt }}
                <button type="button" class="chip-x" @click="removeSymbol(vt)">×</button>
              </span>
            </div>
            <div class="add-row">
              <input v-model="symbolDraft" placeholder="代码 如 600519.SSE" @keydown.enter.prevent="addSymbol" />
              <button type="button" class="ghost" @click="addSymbol">添加</button>
            </div>
            <div class="actions">
              <button type="button" class="primary" :disabled="acting" @click="saveEdit(p.id)">保存</button>
              <button type="button" class="ghost" :disabled="acting" @click="cancelEdit">取消</button>
            </div>
          </template>

          <template v-else>
            <div class="syms">
              <span v-for="s in p.symbols" :key="s.vt_symbol" class="chip">{{ s.vt_symbol }}</span>
            </div>
            <p v-if="p.notes" class="muted">{{ p.notes }}</p>
            <div class="actions">
              <button
                v-if="p.status === 'draft'"
                type="button"
                class="primary"
                :disabled="acting"
                @click="activate(p.id)"
              >
                激活
              </button>
              <button type="button" class="ghost" :disabled="acting" @click="startEdit(p)">编辑</button>
              <button type="button" class="ghost" :disabled="acting" @click="abandon(p.id)">废弃</button>
            </div>
          </template>
        </div>

        <div v-if="historyPlans.length" class="history">
          <button type="button" class="ghost" @click="historyOpen = !historyOpen">
            {{ historyOpen ? '收起历史' : `历史（${historyPlans.length}）` }}
          </button>
          <div v-if="historyOpen" class="plan muted-block" v-for="p in historyPlans" :key="p.id">
            <strong>{{ p.trade_date }}</strong>
            <span class="badge" data-status="abandoned">abandoned</span>
            <div class="syms">
              <span v-for="s in p.symbols" :key="s.vt_symbol" class="chip">{{ s.vt_symbol }}</span>
            </div>
            <p v-if="p.notes" class="muted">{{ p.notes }}</p>
          </div>
        </div>
      </section>
```

补充 CSS：`.ok`（成功色）、`.plan.active`、`.badge`、`.actions`、`.field`、`.chip-x`、`.history`。abandoned 无写按钮。

- [ ] **Step 4: 前端 build**

Run: `cd frontend && npm run build`  
Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/content.ts frontend/src/views/PlaybookView.vue
git commit -m "$(cat <<'EOF'
feat(playbook): 计划区支持激活废弃与轻编辑

打通 draft→active，自选计划外可生效。
EOF
)"
```

---

### Task 6: 文档与总验收

**Files:**
- Modify: `docs/product-roadmap.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: 路线图**

在近期待办末尾（#41 后）追加：

```markdown
42. ~~交易计划生命周期闭环~~（已完成 → [spec](./superpowers/specs/2026-08-13-trading-plan-lifecycle-design.md)）
```

- [ ] **Step 2: smoke**

在 `## 6. 内容 · 回测 · AI · 运维` 的 playbook 条后加：

```markdown
- [ ] `/playbook` 交易计划：draft 可编辑/激活/废弃；激活后 status=active；同日再激活其它 draft 会废弃旧 active；active 可改标的；abandoned 在「历史」只读；激活后 `/watchlist` 持仓不在计划内可见「计划外」
```

- [ ] **Step 3: check.sh**

Run: `./scripts/check.sh`  
Expected: pytest + frontend build 绿

- [ ] **Step 4: Commit**

```bash
git add docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录交易计划生命周期闭环完成

更新路线图 #42 与 smoke 守则激活验收项。
EOF
)"
```

---

## Spec coverage（自检）

| Spec 要求 | Task |
|-----------|------|
| 状态机 activate/abandon/替换 | 2 |
| PATCH notes/pct/symbols 语义 | 3 |
| abandoned 403 | 3 |
| API 三路由 | 4 |
| Playbook UI | 5 |
| 雷达 draft 语义不变 | 未改 plan_draft（回归既有测） |
| off_plan 不改算法 | 未改 off_plan.py |
| roadmap + smoke | 6 |
| 不改自选页 | 遵守 |

## Placeholder scan

无 TBD；symbols 省略语义已写明；mock 与 `db.scalars` 以跑通为准可微调。
