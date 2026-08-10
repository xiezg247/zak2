# Hub 硬过滤行业勾选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** Hub 可勾选 `app.stock_industry` 行业白名单，与硬过滤模板 merge 后参与选股。

**Architecture:** `list_industry_names` + `GET /screener/industries`；`resolve_hard_filter` 支持 template+prefs 字段覆盖；ScreenerHub checkbox + 运行/方案带 `allowed_industries`。

**Tech Stack:** FastAPI、Pydantic `exclude_unset`、Vue ScreenerHubView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-hub-industry-filter-design.md`

## Global Constraints

- 只改 zak2；不改 zak
- 不改 `apply_hard_filters` 空 industry 放行语义
- Commit 仅用户明确要求时（默认跳过）
- 不打真网

**Clarification — HardFilterPrefs partial body：**  
客户端只传 `{ "allowed_industries": "白酒" }` 时，Pydantic 会给其它字段默认值。merge **必须**用 `model_dump(exclude_unset=True)`，否则会用默认 `min_amount_wan=3000` 等覆盖模板。测试需覆盖此点。

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/stock_industry.py` | `list_industry_names` |
| `backend/app/services/hard_filters.py` | `resolve_hard_filter` merge |
| `backend/app/schemas/screener.py` | `IndustryListOut`（可选） |
| `backend/app/api/v1/screener.py` | GET industries |
| `backend/tests/test_hard_filters_resolve.py` | **新建** resolve + list 测 |
| `backend/tests/test_stock_industry.py` | 扩展 list 测 |
| `frontend/src/api/screener.ts` | `industries()` |
| `frontend/src/views/ScreenerHubView.vue` | UI + body/scheme |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: list + resolve merge + API

**Files:**
- Modify: `stock_industry.py`, `hard_filters.py`, `schemas/screener.py`, `api/v1/screener.py`
- Create: `backend/tests/test_hard_filters_resolve.py`
- Modify: `backend/tests/test_stock_industry.py`（可选 list 单测）

**Interfaces:**
- `list_industry_names(db) -> list[str]`
- `resolve_hard_filter(prefs, template_id)` 按 spec 四分支
- `IndustryListOut(items: list[str])`
- `GET /screener/industries`

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_hard_filters_resolve.py
from app.schemas.screener import HardFilterPrefs
from app.services.hard_filters import resolve_hard_filter


def test_resolve_template_only() -> None:
    p = resolve_hard_filter(None, "conservative")
    assert p.min_amount_wan == 5000.0
    assert p.allowed_industries == ""


def test_resolve_merge_industries_keep_template_amounts() -> None:
    # 模拟 Hub：只传 allowed_industries（exclude_unset）
    overlay = HardFilterPrefs.model_validate({"allowed_industries": "白酒,银行"})
    # 注意：model_validate 会 set 所有字段；测试应用 model_construct 或
    # HardFilterPrefs(allowed_industries="白酒,银行") 再检查 __pydantic_fields_set__
    overlay = HardFilterPrefs(allowed_industries="白酒,银行")
    # 确保只有 allowed_industries 在 fields_set：
    assert overlay.model_fields_set == {"allowed_industries"} or "allowed_industries" in overlay.model_fields_set
    p = resolve_hard_filter(overlay, "conservative")
    assert p.allowed_industries == "白酒,银行"
    assert p.min_amount_wan == 5000.0  # 仍来自 conservative
    assert p.min_total_mv_yi == 100.0


def test_resolve_prefs_only() -> None:
    p = resolve_hard_filter(HardFilterPrefs(min_amount_wan=1, allowed_industries="x"), None)
    assert p.min_amount_wan == 1
    assert p.allowed_industries == "x"
```

```python
# test_stock_industry.py 追加
def test_list_industry_names() -> None:
    db = MagicMock()
    db.execute.return_value.scalars.return_value = ["白酒", "银行"]
    # 或按实现用 mappings；与实现一致
    ...
```

实现 `resolve` 时：

```python
def resolve_hard_filter(prefs=None, template_id=None) -> HardFilterPrefs:
    tmpl = _TEMPLATE_MAP.get(template_id) if template_id else None
    if prefs is None and tmpl is None:
        return _TEMPLATE_MAP["balanced"].prefs.model_copy()
    if prefs is None:
        return tmpl.prefs.model_copy()  # type: ignore
    if tmpl is None:
        return prefs
    base = tmpl.prefs.model_copy()
    for key, val in prefs.model_dump(exclude_unset=True).items():
        setattr(base, key, val)
    return base
```

**注意：** FastAPI 解析 JSON `{"allowed_industries":"白酒"}` 时，未出现的字段通常 **unset**（Pydantic v2）。单测用 `HardFilterPrefs(allowed_industries=...)` 时其它字段会进入 fields_set——应用：

```python
HardFilterPrefs.model_construct()  # 不行
# 正确测法：
p = HardFilterPrefs.model_validate({"allowed_industries": "白酒"})
# 在 Pydantic v2，model_validate dict 只 set 提供的键 → fields_set == {"allowed_industries"}
```

先在实现前用一行确认项目 pydantic 行为；若 `model_validate` 仍 set 全部，改用：

```python
HardFilterPrefs.model_construct(allowed_industries="白酒")
# 并手动：object.__setattr__ 或 model_copy(update=..., deep=...) 
```

推荐测法：直接构造再 `model_dump(exclude_unset=True)` 断言——若失败则在 API 层用自定义依赖。实现以「JSON 局部 body」为准。

- [ ] **Step 2: RED → 实现 → GREEN**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_hard_filters_resolve.py tests/test_stock_industry.py -q
```

- [ ] **Step 3: Commit** — 跳过

---

### Task 2: ScreenerHub UI

**Files:**
- Modify: `frontend/src/api/screener.ts`
- Modify: `frontend/src/views/ScreenerHubView.vue`

**Interfaces:**
- `screenerApi.industries(): Promise<{ items: string[] }>`
- State: `industryOptions`, `selectedIndustries: Set/string[]`, `industryOpen`, `industryErr`
- `hardFilterOverride(): { allowed_industries: string } | undefined`
- 所有 run* body 合并；`buildSchemeConfig` / `applyScheme` 读写 `allowed_industries`

UI：硬过滤模板下方可折叠 checkbox 区；空列表提示同步行业映射。

- [ ] **Step 1: 实现 + build**

```bash
cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build
```

- [ ] **Step 2: Commit** — 跳过

---

### Task 3: gap / smoke + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`, `docs/smoke-checklist.md`

- [ ] **Step 1: gap** — Hub 可勾选行业；建议下一刀另定  
- [ ] **Step 2: smoke** — 同步后勾选过滤；不勾选不变  
- [ ] **Step 3: 全量 pytest**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest -q
```

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage

| Spec | Task |
|------|------|
| list + GET industries | 1 |
| resolve merge exclude_unset | 1 |
| Hub checkbox + run/scheme | 2 |
| gap/smoke | 3 |

## Placeholder scan

无 TBD（Pydantic fields_set 行为在 Task1 实现时用一行验证并固定测法）。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-10-hub-industry-filter.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）**  
2. **Inline Execution**  

Which approach?
