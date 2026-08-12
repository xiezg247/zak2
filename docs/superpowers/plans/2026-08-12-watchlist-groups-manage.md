# 自选分组管理闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自选分组支持改名（PATCH）、UI 删组与选中行入组/出组。

**Architecture:** `watchlist_repo.rename_group` + API PATCH；前端补齐 `renameGroup` / `removeFromGroup` 与 `WatchlistView` 控件；复用已有 delete/add member。

**Tech Stack:** FastAPI、SQLAlchemy、Vue 3、pytest mock

**Spec:** `docs/superpowers/specs/2026-08-12-watchlist-groups-manage-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不做分组排序、批量移组、全部视图下选目标组
- 删组不删自选标的
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/schemas/watchlist.py` | `GroupRename` |
| `backend/app/services/watchlist_repo.py` | `rename_group` |
| `backend/app/api/v1/watchlist.py` | PATCH 路由 |
| `backend/tests/test_watchlist_groups.py` | rename 单测 |
| `frontend/src/api/watchlist.ts` | 客户端方法 |
| `frontend/src/views/WatchlistView.vue` | UI |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: `rename_group` + PATCH + 单测

**Files:**
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/services/watchlist_repo.py`
- Modify: `backend/app/api/v1/watchlist.py`
- Create: `backend/tests/test_watchlist_groups.py`

**Interfaces:**
- Produces: `GroupRename`；`rename_group(db, user_id, group_id, name) -> WatchlistGroup`；`PATCH .../groups/{group_id}`
- Consumes: 现有 `WatchlistGroup` / `list_groups` 模式

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_watchlist_groups.py
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.watchlist import WatchlistGroup
from app.services import watchlist_repo as repo


def _group(*, gid: str | None = None, name: str = "A", user_id: str = "u1") -> WatchlistGroup:
    g = WatchlistGroup(id=gid or str(uuid4()), user_id=user_id, name=name, sort_order=0)
    return g


def test_rename_success() -> None:
    db = MagicMock()
    g = _group(name="旧名")
    others: list[WatchlistGroup] = []
    with patch.object(repo, "list_groups", return_value=others):
        db.scalar.return_value = g
        out = repo.rename_group(db, "u1", g.id, "新名")
    assert out.name == "新名"
    db.commit.assert_called()
    db.refresh.assert_called()


def test_rename_empty() -> None:
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        repo.rename_group(db, "u1", "g1", "  ")
    assert ei.value.status_code == 400


def test_rename_not_found() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as ei:
        repo.rename_group(db, "u1", "missing", "名")
    assert ei.value.status_code == 404


def test_rename_conflict() -> None:
    db = MagicMock()
    g = _group(name="旧")
    other = _group(name="已有")
    db.scalar.return_value = g
    with patch.object(repo, "list_groups", return_value=[g, other]):
        with pytest.raises(HTTPException) as ei:
            repo.rename_group(db, "u1", g.id, "已有")
    assert ei.value.status_code == 409
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_watchlist_groups.py -v
```

Expected: FAIL（`rename_group` 不存在）

- [ ] **Step 3: Schema + repo + 路由**

`schemas/watchlist.py`：

```python
class GroupRename(BaseModel):
    name: str = Field(min_length=1, max_length=40)
```

`watchlist_repo.py`（放在 `create_group` 后）：

```python
def rename_group(db: Session, user_id: str, group_id: str, name: str) -> WatchlistGroup:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分组名不能为空")
    row = db.scalar(
        select(WatchlistGroup).where(WatchlistGroup.user_id == user_id, WatchlistGroup.id == group_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="分组不存在")
    groups = list_groups(db, user_id)
    if any(g.id != group_id and g.name.lower() == name.lower() for g in groups):
        raise HTTPException(status_code=409, detail="分组名已存在")
    row.name = name
    db.commit()
    db.refresh(row)
    return row
```

`api/v1/watchlist.py`：import `GroupRename`；在 `post_group` 后：

```python
@router.patch("/watchlist/groups/{group_id}", response_model=GroupOut)
def patch_group(
    group_id: str,
    body: GroupRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    g = repo.rename_group(db, str(user.id), group_id, body.name)
    return GroupOut(id=g.id, name=g.name, sort_order=g.sort_order)
```

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_watchlist_groups.py -q
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/watchlist.py backend/app/services/watchlist_repo.py \
  backend/app/api/v1/watchlist.py backend/tests/test_watchlist_groups.py
git commit -m "$(cat <<'EOF'
feat(watchlist): 支持分组改名 PATCH

rename_group 校验空名与重名；单测覆盖。
EOF
)"
```

---

### Task 2: 前端 API + WatchlistView UI

**Files:**
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`

**Interfaces:**
- Consumes: Task 1 PATCH；已有 DELETE group / members
- Produces: UI 改名/删组/入组/出组

- [ ] **Step 1: API 客户端**

```typescript
renameGroup: (id: string, name: string) =>
  api<WatchlistGroup>(`/api/v1/watchlist/groups/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  }),
removeFromGroup: (groupId: string, vtSymbol: string) =>
  api<{ ok: boolean }>(
    `/api/v1/watchlist/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(vtSymbol)}`,
    { method: 'DELETE' },
  ),
```

（`deleteGroup` / `addToGroup` 已存在。）

- [ ] **Step 2: View 逻辑**

在 script 增加（靠近 `onCreateGroup`）：

```typescript
async function onRenameGroup() {
  if (!groupId.value) return
  const cur = groups.value.find((g) => g.id === groupId.value)
  const next = window.prompt('新分组名', cur?.name || '')
  if (next == null) return
  const name = next.trim()
  if (!name) {
    error.value = '分组名不能为空'
    return
  }
  try {
    error.value = ''
    await watchlistApi.renameGroup(groupId.value, name)
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '改名失败'
  }
}

async function onDeleteGroup() {
  if (!groupId.value) return
  if (!window.confirm('确定删除该分组？自选标的不会被删除')) return
  try {
    error.value = ''
    await watchlistApi.deleteGroup(groupId.value)
    groupId.value = ''
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '删组失败'
  }
}

async function onAddToGroup() {
  if (!groupId.value || !selected.value) return
  try {
    error.value = ''
    await watchlistApi.addToGroup(groupId.value, selected.value.vt_symbol)
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加入分组失败'
  }
}

async function onRemoveFromGroup() {
  if (!groupId.value || !selected.value) return
  try {
    error.value = ''
    await watchlistApi.removeFromGroup(groupId.value, selected.value.vt_symbol)
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '移出分组失败'
  }
}
```

- [ ] **Step 3: 模板（分组 block 内，`groupId` 非空时）**

```html
<div v-if="groupId" class="row">
  <button type="button" class="ghost" @click="onRenameGroup">改名</button>
  <button type="button" class="ghost" @click="onDeleteGroup">删组</button>
</div>
<div v-if="groupId && selected" class="row">
  <button type="button" class="ghost" @click="onAddToGroup">加入此组</button>
  <button type="button" class="ghost" @click="onRemoveFromGroup">移出此组</button>
</div>
```

- [ ] **Step 4: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/watchlist.ts frontend/src/views/WatchlistView.vue
git commit -m "$(cat <<'EOF'
feat(watchlist): 分组改名删组与入出组 UI

筛选分组时可改名删除；选中行可加入或移出当前组。
EOF
)"
```

---

### Task 3: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在自选节增加：

```markdown
- [ ] `/watchlist` 选中某分组：可改名、删组（confirm，标的仍在全部自选）；选中行可「加入此组」「移出此组」
```

- [ ] **Step 2: roadmap**

`10. ~~自选分组管理闭环~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-groups-manage-design.md)）`

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: 全绿

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 记录自选分组管理闭环完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| rename + PATCH + 测试 | 1 |
| UI 改名/删组/入出组 | 2 |
| 文档 + check | 3 |

无 TBD。
