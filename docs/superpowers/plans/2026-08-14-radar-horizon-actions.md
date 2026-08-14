# 雷达展望行动化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 展望/预测表行级「自选」「草案」；`draft-append` 确保次日 draft 并追加标的。

**Architecture:** `plan_draft.append_symbol_to_draft` + `POST /playbook/plans/draft-append`；RadarView 两表操作列复用 `addWatchTo` 与新 API。

**Tech Stack:** FastAPI、SQLAlchemy、Vue 3、pytest

**Spec:** `docs/superpowers/specs/2026-08-14-radar-horizon-actions-design.md`

## Global Constraints

- 只改 zak2；不下单；不做批量；不做 AI
- trade_date 用 `resolve_next_trade_date`；append **不**因冰点/退潮拒绝
- 上限 `MAX_PLAN_SYMBOLS`（`plan_manage` 的 20）；已存在幂等 `added=false`
- 工具栏「生成次日计划草案」覆盖语义不变
- commit 简体中文；`./scripts/check.sh` 绿

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/plan_draft.py` | `append_symbol_to_draft` |
| `backend/app/schemas/content.py` | In/Out |
| `backend/app/api/v1/content.py` | 路由 |
| `backend/tests/test_plan_draft.py` | 单测 |
| `frontend/src/api/content.ts` | `draftAppend` |
| `frontend/src/views/RadarView.vue` | 操作列 |
| docs | #56、smoke、spec |

---

### Task 1: `append_symbol_to_draft` + 测试

**Files:**
- Modify: `backend/app/services/plan_draft.py`
- Modify: `backend/tests/test_plan_draft.py`
- Consumes: `resolve_next_trade_date`、`DEFAULT_PLAN_MAX_POSITION_PCT`、`parse_flexible_symbol`、`TradingPlan`/`TradingPlanSymbol`
- Produces: `append_symbol_to_draft(db, user_id, *, vt_symbol, name=None, source=None) -> dict`

**返回 dict 字段：** `added: bool`, `plan_id: str`, `trade_date: str`, `symbol_count: int`, `message: str`, `status: "draft"`

- [x] **Step 1: 写失败测试**

```python
def test_append_creates_empty_draft_then_adds() -> None:
    db = MagicMock()
    db.scalar.return_value = None  # 无既有 draft
    # scalars 空列表 → 无既有 symbols
    db.scalars.return_value = []
    with patch.object(pd, "resolve_next_trade_date", return_value=("2026-08-17", False)):
        out = pd.append_symbol_to_draft(db, "u1", vt_symbol="600519.SSE", source="horizon")
    assert out["added"] is True
    assert out["trade_date"] == "2026-08-17"
    assert out["symbol_count"] == 1
    db.add.assert_called()  # plan + symbol
    db.commit.assert_called()


def test_append_idempotent_when_already_in_draft() -> None:
    db = MagicMock()
    plan = MagicMock()
    plan.id = "p1"
    plan.trade_date = "2026-08-17"
    db.scalar.return_value = plan
    sym = MagicMock()
    sym.symbol = "600519"
    sym.exchange = "SSE"
    db.scalars.return_value = [sym]
    with (
        patch.object(pd, "resolve_next_trade_date", return_value=("2026-08-17", False)),
        patch("app.services.plan_draft.to_vt_symbol", side_effect=lambda c, e: f"{c}.{e}"),
    ):
        # 若实现用 to_vt_symbol 自 symbols 模块，按实际 patch 路径调整
        out = pd.append_symbol_to_draft(db, "u1", vt_symbol="600519.SSE")
    assert out["added"] is False
    assert "已在" in out["message"]


def test_append_rejects_when_full() -> None:
    from app.services.plan_manage import MAX_PLAN_SYMBOLS
    db = MagicMock()
    plan = MagicMock()
    plan.id = "p1"
    db.scalar.return_value = plan
    # 20 个不同 vt 的假 symbol
    fake = []
    for i in range(MAX_PLAN_SYMBOLS):
        s = MagicMock()
        s.symbol = f"{i:06d}"
        s.exchange = "SSE"
        fake.append(s)
    db.scalars.return_value = fake
    with (
        patch.object(pd, "resolve_next_trade_date", return_value=("2026-08-17", False)),
        patch("app.services.symbols.to_vt_symbol", side_effect=lambda c, e: f"{c}.{e}"),
    ):
        with pytest.raises(HTTPException) as ei:
            pd.append_symbol_to_draft(db, "u1", vt_symbol="600519.SSE")
        assert ei.value.status_code == 400


def test_append_ice_stage_still_ok() -> None:
    """append 不调用情绪拒绝。"""
    db = MagicMock()
    db.scalar.return_value = None
    db.scalars.return_value = []
    with (
        patch.object(pd, "resolve_next_trade_date", return_value=("2026-08-17", False)),
        patch("app.services.plan_draft.build_emotion_cycle") as emo,
    ):
        out = pd.append_symbol_to_draft(db, "u1", vt_symbol="600519.SSE")
    assert out["added"] is True
    emo.assert_not_called()
```

（实现时按真实 ORM 查询写法微调 mock：`db.scalars(select...).all()` 等。）

- [x] **Step 2: Run 确认失败**

```bash
cd backend && uv run pytest tests/test_plan_draft.py::test_append_creates_empty_draft_then_adds -q
```

Expected: FAIL（函数未定义）

- [x] **Step 3: 实现**

```python
def append_symbol_to_draft(
    db: Session,
    user_id: str,
    *,
    vt_symbol: str,
    name: str | None = None,
    source: str | None = None,
) -> dict:
    from app.services.plan_manage import MAX_PLAN_SYMBOLS
    from app.services.symbols import parse_flexible_symbol, to_vt_symbol

    try:
        code, exch = parse_flexible_symbol(vt_symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    vt = to_vt_symbol(code, exch)
    td, _ = resolve_next_trade_date(db)
    now = _now()
    plan = db.scalar(
        select(TradingPlan)
        .where(
            TradingPlan.user_id == user_id,
            TradingPlan.trade_date == td,
            TradingPlan.status == "draft",
        )
        .order_by(desc(TradingPlan.updated_at))
        .limit(1)
    )
    if plan is None:
        plan = TradingPlan(
            id=uuid.uuid4().hex,
            user_id=user_id,
            trade_date=td,
            emotion_expected="",
            max_position_pct=DEFAULT_PLAN_MAX_POSITION_PCT,
            notes="展望行追加",
            status="draft",
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
        db.flush()

    existing = list(
        db.scalars(
            select(TradingPlanSymbol).where(
                TradingPlanSymbol.plan_id == plan.id,
                TradingPlanSymbol.user_id == user_id,
            ).order_by(TradingPlanSymbol.sort_order)
        )
    )
    vts = [to_vt_symbol(s.symbol, s.exchange) for s in existing]
    if vt in vts:
        return {
            "added": False,
            "plan_id": plan.id,
            "trade_date": td,
            "symbol_count": len(vts),
            "status": "draft",
            "message": f"已在草案 {vt}",
        }
    if len(vts) >= MAX_PLAN_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"标的最多 {MAX_PLAN_SYMBOLS} 只")

    entry = ""
    if source == "predict":
        entry = "来自规则预测"
    elif source == "horizon":
        entry = "来自共振展望"
    db.add(
        TradingPlanSymbol(
            plan_id=plan.id,
            symbol=code,
            exchange=exch,
            user_id=user_id,
            allowed_modes="",
            entry_conditions=entry,
            exit_conditions="",
            sort_order=len(existing),
        )
    )
    plan.updated_at = now
    db.commit()
    return {
        "added": True,
        "plan_id": plan.id,
        "trade_date": td,
        "symbol_count": len(vts) + 1,
        "status": "draft",
        "message": f"已加入草案 {vt}",
    }
```

- [x] **Step 4: 测试绿**

```bash
cd backend && uv run pytest tests/test_plan_draft.py -q
```

- [x] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(plan): 增加草案单标的追加 append_symbol_to_draft

无 draft 则建空稿；已在幂等；满员拒绝。
EOF
)"
```

---

### Task 2: Schema + API 路由

**Files:**
- Modify: `backend/app/schemas/content.py`
- Modify: `backend/app/api/v1/content.py`
- Test: 可在 `test_plan_draft.py` 加 API 客户端测（仿现有 `post_radar_plan_draft`）

**Interfaces:**

```python
class PlanDraftAppendIn(BaseModel):
    vt_symbol: str
    name: str | None = None
    source: str | None = None  # horizon | predict

class PlanDraftAppendOut(BaseModel):
    added: bool
    plan_id: str
    trade_date: str
    symbol_count: int
    status: str = "draft"
    message: str = ""
```

```python
@router.post("/playbook/plans/draft-append", response_model=PlanDraftAppendOut)
def post_draft_append(body: PlanDraftAppendIn, user=..., db=...):
    return PlanDraftAppendOut(**plan_draft_svc.append_symbol_to_draft(...))
```

- [x] **Step 1: 实现 + API 测**

```python
def test_api_draft_append(monkeypatch) -> None:
    client = _api_client()
    with patch(
        "app.api.v1.content.plan_draft_svc.append_symbol_to_draft",
        return_value={
            "added": True,
            "plan_id": "p1",
            "trade_date": "2026-08-17",
            "symbol_count": 1,
            "status": "draft",
            "message": "已加入草案 600519.SSE",
        },
    ):
        r = client.post(
            "/api/v1/playbook/plans/draft-append",
            json={"vt_symbol": "600519.SSE", "source": "horizon"},
        )
    assert r.status_code == 200
    assert r.json()["added"] is True
```

（确认 `content` 模块已 import `plan_draft as plan_draft_svc`。）

- [x] **Step 2: pytest 绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(api): 增加 POST playbook/plans/draft-append

展望行追加次日草案标的。
EOF
)"
```

---

### Task 3: RadarView 操作列

**Files:**
- Modify: `frontend/src/api/content.ts`
- Modify: `frontend/src/views/RadarView.vue`

**Interfaces:**

```ts
draftAppend: (body: { vt_symbol: string; name?: string; source?: string }) =>
  api<PlanDraftAppend>('/api/v1/playbook/plans/draft-append', {
    method: 'POST',
    body: JSON.stringify(body),
  })
```

- [x] **Step 1: content.ts 类型 + 方法**

- [x] **Step 2: RadarView**

```ts
const rowActionMsg = ref('')

async function addWatchFromHorizon(vt: string, name?: string) {
  await addWatchTo(vt, name, rowActionMsg)
}

async function appendDraftFromRow(vt: string, name: string | undefined, source: 'horizon' | 'predict') {
  if (!vt || actingVt.value) return
  actingVt.value = vt
  rowActionMsg.value = ''
  try {
    const r = await contentApi.draftAppend({ vt_symbol: vt, name, source })
    rowActionMsg.value = r.message || (r.added ? `已加入草案 ${vt}` : `已在草案 ${vt}`)
  } catch (e) {
    rowActionMsg.value = e instanceof Error ? e.message : '加入草案失败'
  } finally {
    actingVt.value = ''
  }
}
```

模板：两表 `thead` 加「操作」；每行：

```html
<td class="ops">
  <button type="button" class="ghost tiny-btn" :disabled="!!actingVt" @click="addWatchFromHorizon(row.vt_symbol, row.name)">自选</button>
  <button type="button" class="ghost tiny-btn" :disabled="!!actingVt" @click="appendDraftFromRow(row.vt_symbol, row.name, 'horizon')">草案</button>
</td>
```

预测表 `source: 'predict'`。页顶或表旁展示 `rowActionMsg`；若 message 含「草案」可链 `/playbook`（对齐 draftMsg）。

- [x] **Step 3: `npm run build`**

- [x] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ui): 展望与预测表支持入自选与入草案

行级操作复用 watchlist 与 draft-append。
EOF
)"
```

---

### Task 4: 文档收口

**Files:**
- `docs/product-roadmap.md` #56  
- `docs/smoke-checklist.md`  
- spec 状态 → 已批准（已实现）  
- 本 plan checklist

- [x] **Step 1: 文档**

```markdown
56. ~~雷达展望行动化~~（已完成 → [spec](./superpowers/specs/2026-08-14-radar-horizon-actions-design.md)）：行级入自选 + draft-append
```

smoke：`/radar` 展望/预测展开后行可「自选」「草案」；无草案可建；满员/已在有文案。

- [x] **Step 2: `./scripts/check.sh`**

- [x] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(radar): 记录展望行动化完成

更新路线图 #56 与 smoke。
EOF
)"
```

---

## Self-review

1. Spec：append API、两表操作、自选复用、非目标 → Task 1–4。  
2. 无 TBD。  
3. `MAX_PLAN_SYMBOLS` 与 `resolve_next_trade_date` 与既有计划一致。

## Execution

建议 worktree：`feat/radar-horizon-actions`。
