# 选股多因子权重编辑 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 盘中/盘后多因子权重可按用户编辑、持久化，并在跑选股时生效。

**Architecture:** `recipe_weights` 服务（app.meta）+ screener API + engine 加权打分 + ScreenerHub 配方 Tab UI。对齐雷达共振权重交互。

**Tech Stack:** FastAPI、SQLAlchemy text meta、Vue ScreenerHubView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-screener-recipe-weights-design.md`

## Global Constraints

- 只改 zak2；不改 zak
- 仅 `intraday_multi` / `post_close_multi`
- 权重 ≥0、归一化和为 1；PUT `{}` 恢复默认
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/recipe_weights.py` | 默认表、normalize、load/save、payload |
| `backend/app/services/engine.py` | 打分接受 weights |
| `backend/app/schemas/screener.py` | WeightsOut / WeightsPut |
| `backend/app/api/v1/screener.py` | GET/PUT recipes/{id}/weights |
| `backend/tests/test_recipe_weights.py` | 服务+API+engine 测 |
| `frontend/src/api/screener.ts`（或现有 api） | client |
| `frontend/src/views/ScreenerHubView.vue` | 权重面板 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

参考实现：`radar_resonance.py` 的 load/save/validate/weights_payload 模式（本刀用归一化而非 [0,5] clamp）。

---

### Task 1: recipe_weights 服务 + 单测

**Files:**
- Create: `backend/app/services/recipe_weights.py`
- Create: `backend/tests/test_recipe_weights.py`

**Interfaces:**
- `EDITABLE_RECIPES = frozenset({"intraday_multi", "post_close_multi"})`
- `DEFAULT_WEIGHTS: dict[str, dict[str, float]]`（与 spec 表一致）
- `FACTOR_LABELS: dict[str, dict[str, str]]`
- `meta_key(user_id) -> str`  # `screener/recipe_weights/{user_id}`
- `normalize_weights(recipe_id, raw: dict) -> dict[str, float]`  # ValueError 中文
- `load_recipe_weights(db, user_id, recipe_id) -> dict[str, float]`
- `save_recipe_weights(db, user_id, recipe_id, weights: dict) -> dict[str, float]`  # `{}` 删覆盖
- `weights_payload(recipe_id, merged) -> dict`

normalize 规则：
- recipe 非法 → ValueError
- 未知 key → ValueError
- 非有限或 <0 → ValueError
- sum==0 → ValueError
- 返回 `{k: round(v/sum, 4) for k,v in ...}`（缺省 key 用 0 再归一？**要求：PUT 须含全部因子键**，或缺失填 0 再归一；推荐 **缺失用默认值再归一** 更友好 — 采用：**提交的键覆盖默认，未提交键保留默认，再整体归一**）

- [ ] **Step 1: 单测（失败先写）**

```python
from app.services import recipe_weights as rw

def test_normalize_sums_to_one() -> None:
    out = rw.normalize_weights("intraday_multi", {"momentum": 2, "turnover": 2, "volume_ratio": 2, "surge": 2})
    assert abs(sum(out.values()) - 1.0) < 1e-6
    assert all(abs(v - 0.25) < 1e-4 for v in out.values())

def test_normalize_rejects_unknown_key() -> None:
    import pytest
    with pytest.raises(ValueError):
        rw.normalize_weights("intraday_multi", {"nope": 1})

def test_normalize_rejects_all_zero() -> None:
    import pytest
    with pytest.raises(ValueError):
        rw.normalize_weights("intraday_multi", {k: 0 for k in rw.DEFAULT_WEIGHTS["intraday_multi"]})
```

- [ ] **Step 2–4: 实现 + mock load/save meta + GREEN；Commit 跳过**

---

### Task 2: Engine 接入 + API

**Files:**
- Modify: `backend/app/services/engine.py`
- Modify: `backend/app/schemas/screener.py`
- Modify: `backend/app/api/v1/screener.py`
- Modify: `backend/tests/test_recipe_weights.py` / `test_engine.py`

**Engine:**
- `_score_intraday_multi(row, weights=None)` / `_score_post_close_multi(row, weights=None)`
- `run_recipe_screen`：若 recipe 可编辑且 `db` 与 user 可用——**注意**：当前 `run_recipe_screen` 可能无 `user_id`。查调用链：API 层应传入 `user_id` 或在 API 包装里 load weights 再传入。

**Ambiguity resolution（binding）：**
- 给 `run_recipe_screen` 增加可选 `user_id: str | None = None`；当 `db`+`user_id` 且 recipe 可编辑时 load weights。
- API `run` 路由传入 `str(user.id)`。
- 单测可直接传 `weights=` 参数到 scorer，或 patch load。

**Schemas:**

```python
class RecipeWeightItem(BaseModel):
    key: str
    label: str
    weight: float
    default_weight: float

class RecipeWeightsOut(BaseModel):
    recipe_id: str
    items: list[RecipeWeightItem]
    weights: dict[str, float]

class RecipeWeightsPut(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)
```

**Routes:** `GET/PUT /screener/recipes/{recipe_id}/weights`

- [ ] **TDD API + engine 排序受权重影响；Commit 跳过**

---

### Task 3: 前端 + 文档 + 全量

**Files:**
- `frontend/src/api/screener.ts`（或现有 screener api 模块）
- `frontend/src/views/ScreenerHubView.vue`
- `docs/gap-vs-desktop.md` / `smoke-checklist.md`

**UI：**
- `isWeightEditable` = recipe ∈ intraday/post_close
- 加载/保存/恢复默认；空 draft 不 PUT 清空
- 样式贴近现有 Hub / 共振侧栏

**Docs：** gap 多因子行更新；smoke 加权重编辑项

- [ ] **npm run build + 全量 pytest；Commit 跳过**

---

## Spec coverage

| Spec | Task |
|------|------|
| normalize / meta load-save | 1 |
| engine + API | 2 |
| Hub UI + docs | 3 |

无 TBD。
