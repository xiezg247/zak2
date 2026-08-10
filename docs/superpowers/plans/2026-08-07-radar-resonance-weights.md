# 雷达共振权重 UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 按用户持久化雷达共振卡片权重；侧栏可调并立即重算共振。

**Architecture:** `app.meta` 键 `radar/resonance_weights/{user_id}`；服务层 load/save/merge；`compute_resonance` 接受 weights；GET/PUT `/radar/resonance/weights`；Radar 侧栏数字输入。

**Tech Stack:** FastAPI、SQLAlchemy/`app.meta`、Vue RadarView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-radar-resonance-weights-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 无新表 / 无短线预设 / 无独立设置页
- 权重钳制 `[0, 5]`，2 位小数；默认可编 = `CARD_WEIGHTS` 中 `>0`
- `PUT weights: {}` → 删除 meta 键
- Commit 仅在用户明确要求时执行（本计划步骤默认跳过 commit）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/radar_resonance.py` | 标签、`editable_card_ids`、merge/validate、load/save meta、`compute_resonance(weights=)`、`list_radar_resonance(user_id=)` |
| `backend/app/schemas/market.py` | `RadarResonanceWeightItem` / `RadarResonanceWeightsOut` / `RadarResonanceWeightsPut` |
| `backend/app/api/v1/market.py` | GET/PUT weights；resonance 传 `user_id` |
| `backend/tests/test_radar_resonance.py` | 扩展单测 |
| `backend/tests/test_radar_resonance_weights.py` | 持久化 / API 校验单测 |
| `frontend/src/api/market.ts` | weights API |
| `frontend/src/views/RadarView.vue` | 侧栏权重面板 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: 权重 merge/validate + compute 注入

**Files:**
- Modify: `backend/app/services/radar_resonance.py`
- Modify: `backend/tests/test_radar_resonance.py`
- Create: `backend/tests/test_radar_resonance_weights.py`（本任务先写纯函数测；meta 读写可同文件）

**Interfaces:**
- Produces:
  - `CARD_TITLES: dict[str, str]`
  - `editable_card_ids() -> list[str]`（`CARD_WEIGHTS` 中 `>0`，稳定排序）
  - `merge_weights(stored: object | None) -> dict[str, float]`（全量 CARD_WEIGHTS，覆盖可编卡）
  - `validate_put_weights(raw: dict) -> dict[str, float]`（仅可编卡；非法 raise `ValueError` 中文）
  - `meta_key(user_id: str) -> str` → `radar/resonance_weights/{user_id}`
  - `load_user_weights(db, user_id) -> dict[str, float]`
  - `save_user_weights(db, user_id, weights: dict) -> dict[str, float]`（空 dict → DELETE meta；非空 → 存完整可编子集 JSON）
  - `weights_payload(merged) -> dict` 含 `items` / `weights`（items 仅可编）
  - `compute_resonance(..., weights: dict[str, float] | None = None)`
  - `list_radar_resonance(db, *, user_id: str, min_cards=..., top_n=...)`

**CARD_TITLES（写死）：**

```python
CARD_TITLES = {
    "leader_pick": "选股·龙头",
    "discovery_limit_ladder": "发现·连板梯队",
    "discovery_limit_break": "发现·炸板断板",
    "discovery_change_top": "发现·涨幅前列",
    "discovery_volume_surge": "发现·放量异动",
    "discovery_moneyflow_intraday": "发现·资金异动",
    "watchlist_short_term": "自选·短线关注",
    "watchlist_intraday": "自选·异动",
    "sector_flow_hot": "板块·资金热度",
    "sector_theme": "板块·主线",
}
```

- [ ] **Step 1: 写失败单测**

```python
# tests/test_radar_resonance_weights.py
import pytest
from app.services import radar_resonance as rr


def test_merge_weights_defaults() -> None:
    m = rr.merge_weights(None)
    assert m["leader_pick"] == 1.5
    assert m["sector_flow_hot"] == 0.0


def test_merge_weights_override() -> None:
    m = rr.merge_weights({"leader_pick": 3, "sector_flow_hot": 9})
    assert m["leader_pick"] == 3.0
    assert m["sector_flow_hot"] == 0.0  # 不可编，忽略覆盖


def test_validate_put_ok() -> None:
    out = rr.validate_put_weights({"leader_pick": 2.5, "discovery_limit_ladder": 1})
    assert out["leader_pick"] == 2.5
    assert "sector_flow_hot" not in out


def test_validate_put_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="未知"):
        rr.validate_put_weights({"no_such_card": 1})


def test_validate_put_rejects_oob() -> None:
    with pytest.raises(ValueError, match="范围"):
        rr.validate_put_weights({"leader_pick": 6})


def test_compute_resonance_custom_weights() -> None:
    from app.schemas.market import RadarCardOut

    cards = [
        RadarCardOut(
            card_id="leader_pick",
            title="龙头",
            source="synthesized",
            rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}],
        ),
        RadarCardOut(
            card_id="discovery_change_top",
            title="涨幅",
            source="cache",
            rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}],
        ),
    ]
    low = rr.compute_resonance(
        cards, min_cards=1, top_n=5, weights={**rr.CARD_WEIGHTS, "leader_pick": 0.1, "discovery_change_top": 0.1}
    )
    high = rr.compute_resonance(
        cards, min_cards=1, top_n=5, weights={**rr.CARD_WEIGHTS, "leader_pick": 5.0, "discovery_change_top": 5.0}
    )
    assert high.entries[0].resonance_score > low.entries[0].resonance_score
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_radar_resonance_weights.py -q
```

Expected: FAIL（缺符号）

- [ ] **Step 3: 实现纯函数 + meta 读写 + 改 `compute_resonance` / `list_radar_resonance`**

`validate_put_weights`：
- 值必须可 float；`<0` 或 `>5` → `ValueError("权重超出范围 [0, 5]")`
- card 不在可编集合 → `ValueError("未知或不可编辑的卡片：…")`
- 返回 round(v, 2) 的可编子集（调用方可再补全默认后 save）

`save_user_weights`：
- 若 `weights == {}`：`DELETE FROM app.meta WHERE key=:k`；commit；return `merge_weights(None)`
- 否则：`validate` → 与默认可编合并成完整可编子集 → JSON upsert；return `merge_weights(payload)`

`compute_resonance` 循环内：
```python
table = weights if weights is not None else CARD_WEIGHTS
weight = float(table.get(card.card_id, CARD_WEIGHTS.get(card.card_id, 1.0)))
```

`list_radar_resonance` 增加 `user_id: str`，`weights=load_user_weights(db, user_id)`。

另补 meta 单测（MagicMock db）：

```python
def test_save_empty_deletes(monkeypatch) -> None:
    db = MagicMock()
    # execute 捕获 DELETE；或 patch
    ...
```

（实现者可用 MagicMock 断言 SQL 文本含 DELETE / INSERT。）

- [ ] **Step 4: 跑测**

```bash
cd backend && uv run pytest tests/test_radar_resonance_weights.py tests/test_radar_resonance.py -q
```

Expected: PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: API schemas + routes

**Files:**
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/app/api/v1/market.py`
- Modify: `backend/tests/test_radar_resonance_weights.py`（API 或 service 级）

**Interfaces:**
- Consumes: Task 1 load/save/weights_payload/validate
- Produces:
  - `RadarResonanceWeightItem(card_id, title, weight, default_weight)`
  - `RadarResonanceWeightsOut(items, weights)`
  - `RadarResonanceWeightsPut(weights: dict[str, float])`
  - `GET /api/v1/radar/resonance/weights`
  - `PUT /api/v1/radar/resonance/weights`
  - `get_radar_resonance` 传 `user_id=str(user.id)`

- [ ] **Step 1: schema**

```python
class RadarResonanceWeightItem(BaseModel):
    card_id: str
    title: str
    weight: float
    default_weight: float


class RadarResonanceWeightsOut(BaseModel):
    items: list[RadarResonanceWeightItem] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)


class RadarResonanceWeightsPut(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)
```

- [ ] **Step 2: routes**

```python
@router.get("/radar/resonance/weights", response_model=RadarResonanceWeightsOut)
def get_resonance_weights(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    merged = resonance_svc.load_user_weights(db, str(user.id))
    return RadarResonanceWeightsOut(**resonance_svc.weights_payload(merged))


@router.put("/radar/resonance/weights", response_model=RadarResonanceWeightsOut)
def put_resonance_weights(body: RadarResonanceWeightsPut, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        merged = resonance_svc.save_user_weights(db, str(user.id), dict(body.weights or {}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RadarResonanceWeightsOut(**resonance_svc.weights_payload(merged))
```

改 `get_radar_resonance`：
```python
return resonance_svc.list_radar_resonance(
    db, user_id=str(user.id), min_cards=min_cards, top_n=top_n
)
```

注意：路由顺序 — `/radar/resonance/weights` 须注册在可能冲突的动态路径之前（当前无 `{id}` 冲突，放在 `resonance` 附近即可）。

- [ ] **Step 3: 单测 weights_payload + save roundtrip mock**

```python
def test_weights_payload_items_only_editable() -> None:
    merged = rr.merge_weights({"leader_pick": 2})
    payload = rr.weights_payload(merged)
    ids = {i["card_id"] for i in payload["items"]}
    assert "leader_pick" in ids
    assert "sector_flow_hot" not in ids
    assert payload["weights"]["leader_pick"] == 2.0
```

- [ ] **Step 4: 跑测**

```bash
cd backend && uv run pytest tests/test_radar_resonance_weights.py tests/test_radar_resonance.py -q
```

Expected: PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 3: RadarView 权重面板

**Files:**
- Modify: `frontend/src/api/market.ts`
- Modify: `frontend/src/views/RadarView.vue`

- [ ] **Step 1: API client**

```typescript
export type ResonanceWeightItem = {
  card_id: string
  title: string
  weight: number
  default_weight: number
}
export type ResonanceWeights = {
  items: ResonanceWeightItem[]
  weights: Record<string, number>
}

// in marketApi:
resonanceWeights: () => api<ResonanceWeights>('/api/v1/radar/resonance/weights'),
putResonanceWeights: (weights: Record<string, number>) =>
  api<ResonanceWeights>('/api/v1/radar/resonance/weights', {
    method: 'PUT',
    body: JSON.stringify({ weights }),
  }),
```

- [ ] **Step 2: RadarView UI**

- 状态：`weightOpen`、`weightItems`、`weightDraft: Record<string, number>`、`weightBusy`、`weightErr`
- `load` 时并行拉 `resonanceWeights`（失败不挡共振列表）
- 侧栏 head：`可调权重`；按钮切换 `权重` 折叠
- 折叠区内 `v-for` number input；「保存」「恢复默认」
- 保存：从 draft 组 `weights` → PUT → 更新 items/draft → `load` 共振
- 恢复默认：PUT `{}` → 同上

保持现有侧栏列表与加自选不变。

- [ ] **Step 3: build**

```bash
cd frontend && npm run build
```

Expected: OK

- [ ] **Step 4: Commit** — 跳过

---

### Task 4: 文档 + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap** — 共振侧栏备注改为「可调权重（按用户 meta）」；下一刀去掉该项

- [ ] **Step 2: smoke** — `/radar` 可改权重、保存后分数变、刷新仍保留、恢复默认

- [ ] **Step 3: 全量**

```bash
cd backend && uv run pytest -q
cd ../frontend && npm run build
```

Expected: 全绿

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| meta 键 / 完整可编子集 / PUT {} 删键 | 1 |
| merge / 钳制 / 400 | 1–2 |
| GET/PUT weights API | 2 |
| resonance 用用户权重 | 1–2 |
| 侧栏 UI | 3 |
| gap / smoke / pytest+build | 4 |

无 TBD；接口名前后一致。
