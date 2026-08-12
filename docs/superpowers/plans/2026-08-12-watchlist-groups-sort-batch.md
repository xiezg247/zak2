# 自选分组排序与批量移组 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分组上移/下移持久化 `sort_order`；列表多选批量加入/移出分组。

**Architecture:** `reorder_groups` 对齐 `reorder_items`；`batch_group_members` 一次 commit 返回计数；WatchlistView 上下箭头 + checkbox 工具条。

**Tech Stack:** FastAPI、SQLAlchemy、Vue 3、pytest

**Spec:** `docs/superpowers/specs/2026-08-12-watchlist-groups-sort-batch-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不做拖拽、原子换组、删除自选池标的
- 批量部分失败：其余继续；返回 skipped/errors
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/schemas/watchlist.py` | GroupsReorder / Batch schemas |
| `backend/app/services/watchlist_repo.py` | `reorder_groups` / `batch_group_members` |
| `backend/app/api/v1/watchlist.py` | PUT reorder + POST batch |
| `backend/tests/test_watchlist_groups.py` | 扩展测试 |
| `frontend/src/api/watchlist.ts` | API 客户端 |
| `frontend/src/views/WatchlistView.vue` | ↑↓ + 多选批量 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | #28 |

---

### Task 1: 后端分组重排

**Files:**
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/services/watchlist_repo.py`
- Modify: `backend/app/api/v1/watchlist.py`
- Modify: `backend/tests/test_watchlist_groups.py`

**Interfaces:**
- Produces: `reorder_groups(db, user_id, group_ids: list[str]) -> list[WatchlistGroup]`
- Produces: `PUT /api/v1/watchlist/groups/reorder` body `{group_ids}` → `list[GroupOut]`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/test_watchlist_groups.py
def test_reorder_groups_order() -> None:
    db = MagicMock()
    g1 = _group(gid="g1", name="A")
    g1.sort_order = 0
    g2 = _group(gid="g2", name="B")
    g2.sort_order = 1
    with patch.object(repo, "list_groups", return_value=[g1, g2]):
        out = repo.reorder_groups(db, "u1", ["g2", "g1"])
    assert [g.id for g in out] == ["g2", "g1"]
    assert g2.sort_order == 0
    assert g1.sort_order == 1
    db.commit.assert_called()


def test_reorder_groups_ignores_unknown_and_appends() -> None:
    db = MagicMock()
    g1 = _group(gid="g1", name="A")
    g2 = _group(gid="g2", name="B")
    with patch.object(repo, "list_groups", return_value=[g1, g2]):
        out = repo.reorder_groups(db, "u1", ["g2", "missing"])
    assert [g.id for g in out] == ["g2", "g1"]
    assert g2.sort_order == 0
    assert g1.sort_order == 1
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_watchlist_groups.py::test_reorder_groups_order tests/test_watchlist_groups.py::test_reorder_groups_ignores_unknown_and_appends -q
```

Expected: FAIL（`reorder_groups` 不存在）

- [ ] **Step 3: Schema + repo + 路由**

```python
# schemas/watchlist.py
class GroupsReorderRequest(BaseModel):
    group_ids: list[str] = Field(min_length=1, description="分组 id 期望顺序")
```

```python
# watchlist_repo.py — 紧挨 reorder_items / list_groups 附近
def reorder_groups(db: Session, user_id: str, group_ids: list[str]) -> list[WatchlistGroup]:
    groups = {g.id: g for g in list_groups(db, user_id)}
    ordered: list[WatchlistGroup] = []
    seen: set[str] = set()
    for gid in group_ids:
        if gid in groups and gid not in seen:
            ordered.append(groups[gid])
            seen.add(gid)
    for gid, g in groups.items():
        if gid not in seen:
            ordered.append(g)
    for index, g in enumerate(ordered):
        g.sort_order = index
    db.commit()
    return ordered
```

```python
# api/v1/watchlist.py — 放在 GET groups 之前或之后均可；注意 path 勿被 {group_id} 抢占
# 必须注册在 `/watchlist/groups/{group_id}` 之前，或使用字面量 `reorder` 路径：
@router.put("/watchlist/groups/reorder", response_model=list[GroupOut])
def put_groups_reorder(
    body: GroupsReorderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GroupOut]:
    rows = repo.reorder_groups(db, str(user.id), body.group_ids)
    return [GroupOut(id=g.id, name=g.name, sort_order=g.sort_order) for g in rows]
```

导入 `GroupsReorderRequest`。

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_watchlist_groups.py -q
```

Expected: 全部 PASS（含原有 rename 测）

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/watchlist.py backend/app/services/watchlist_repo.py \
  backend/app/api/v1/watchlist.py backend/tests/test_watchlist_groups.py
git commit -m "$(cat <<'EOF'
feat(watchlist): 支持分组 reorder API

PUT /watchlist/groups/reorder 持久化 sort_order。
EOF
)"
```

---

### Task 2: 后端批量成员

**Files:**
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/services/watchlist_repo.py`
- Modify: `backend/app/api/v1/watchlist.py`
- Modify: `backend/tests/test_watchlist_groups.py`

**Interfaces:**
- Produces: `batch_group_members(db, user_id, group_id, symbols, action) -> dict`
- Produces: `POST /watchlist/groups/{group_id}/members/batch`
- Consumes: `parse_flexible_symbol` / `normalize_exchange` / 现有 member 表

- [ ] **Step 1: 写失败测试**

```python
def test_batch_add_counts() -> None:
    db = MagicMock()
    g = _group(gid="g1")
    # scalar: group exists, then in_wl yes, existing member None → add
    from app.models.watchlist import WatchlistItem, WatchlistGroupMember

    item = WatchlistItem(symbol="600519", exchange="SSE", user_id="u1", name="", sort_order=0)

    def scalar_side_effect(stmt):
        # 简化：用 call 次序或 patch 内部 helpers
        return None

    with (
        patch.object(repo, "parse_flexible_symbol", return_value=("600519", "SSE")),
        patch.object(repo, "normalize_exchange", side_effect=lambda e: e),
    ):
        # 更稳：直接 mock db.scalar 序列：group, in_wl, existing
        db.scalar.side_effect = [g, item, None]
        out = repo.batch_group_members(db, "u1", "g1", ["600519.SSE"], "add")
    assert out["ok"] is True
    assert out["action"] == "add"
    assert out["added"] == 1
    assert out["skipped"] == 0
    assert out["errors"] == []
    db.commit.assert_called()
    db.add.assert_called()


def test_batch_add_not_in_watchlist_error() -> None:
    db = MagicMock()
    g = _group(gid="g1")
    db.scalar.side_effect = [g, None]  # group ok, not in wl
    with patch.object(repo, "parse_flexible_symbol", return_value=("600519", "SSE")):
        out = repo.batch_group_members(db, "u1", "g1", ["600519.SSE"], "add")
    assert out["added"] == 0
    assert len(out["errors"]) == 1
    assert "自选" in out["errors"][0]["detail"]


def test_batch_remove_skips_missing() -> None:
    db = MagicMock()
    g = _group(gid="g1")
    db.scalar.side_effect = [g, None]  # group, no member
    with patch.object(repo, "parse_flexible_symbol", return_value=("600519", "SSE")):
        out = repo.batch_group_members(db, "u1", "g1", ["600519.SSE"], "remove")
    assert out["removed"] == 0
    assert out["skipped"] == 1
    db.commit.assert_called()


def test_batch_group_missing_404() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as ei:
        repo.batch_group_members(db, "u1", "missing", ["600519.SSE"], "add")
    assert ei.value.status_code == 404
```

（若 `db.scalar` 次序 fragile，可改为 patch 更小 helper；以断言行为为准。）

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_watchlist_groups.py -k batch -q
```

Expected: FAIL

- [ ] **Step 3: 实现**

```python
# schemas
from typing import Literal

class GroupMembersBatchRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=100)
    action: Literal["add", "remove"]


class GroupMembersBatchError(BaseModel):
    symbol: str
    detail: str


class GroupMembersBatchOut(BaseModel):
    ok: bool = True
    action: Literal["add", "remove"]
    added: int = 0
    removed: int = 0
    skipped: int = 0
    errors: list[GroupMembersBatchError] = Field(default_factory=list)
```

```python
# watchlist_repo.py
def batch_group_members(
    db: Session,
    user_id: str,
    group_id: str,
    symbols: list[str],
    action: str,
) -> dict:
    group = db.scalar(
        select(WatchlistGroup).where(WatchlistGroup.user_id == user_id, WatchlistGroup.id == group_id)
    )
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    added = 0
    removed = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for raw in symbols:
        try:
            symbol, exch = parse_flexible_symbol(raw)
        except Exception:  # noqa: BLE001
            errors.append({"symbol": raw, "detail": "无法解析代码"})
            continue

        if action == "add":
            in_wl = db.scalar(
                select(WatchlistItem).where(
                    WatchlistItem.user_id == user_id,
                    WatchlistItem.symbol == symbol,
                    WatchlistItem.exchange == exch,
                )
            )
            if not in_wl:
                errors.append({"symbol": raw, "detail": "请先加入自选池"})
                continue
            existing = db.scalar(
                select(WatchlistGroupMember).where(
                    WatchlistGroupMember.group_id == group_id,
                    WatchlistGroupMember.symbol == symbol,
                    WatchlistGroupMember.exchange == exch,
                )
            )
            if existing:
                skipped += 1
                continue
            db.add(
                WatchlistGroupMember(
                    user_id=user_id, group_id=group_id, symbol=symbol, exchange=exch
                )
            )
            added += 1
        else:
            row = db.scalar(
                select(WatchlistGroupMember).where(
                    WatchlistGroupMember.user_id == user_id,
                    WatchlistGroupMember.group_id == group_id,
                    WatchlistGroupMember.symbol == symbol,
                    WatchlistGroupMember.exchange == exch,
                )
            )
            if not row:
                skipped += 1
                continue
            db.delete(row)
            removed += 1

    db.commit()
    return {
        "ok": True,
        "action": action,
        "added": added,
        "removed": removed,
        "skipped": skipped,
        "errors": errors,
    }
```

```python
# api — 放在单条 members 路由旁
@router.post("/watchlist/groups/{group_id}/members/batch", response_model=GroupMembersBatchOut)
def post_group_members_batch(
    group_id: str,
    body: GroupMembersBatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupMembersBatchOut:
    raw = repo.batch_group_members(db, str(user.id), group_id, body.symbols, body.action)
    return GroupMembersBatchOut(**raw)
```

注意：FastAPI 路由顺序 — `.../members/batch` 须在 `.../members/{vt_symbol}` **之前**注册，否则 `batch` 会被当成 vt_symbol。

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_watchlist_groups.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/watchlist.py backend/app/services/watchlist_repo.py \
  backend/app/api/v1/watchlist.py backend/tests/test_watchlist_groups.py
git commit -m "$(cat <<'EOF'
feat(watchlist): 分组批量加入/移出成员 API

POST members/batch；部分失败继续并返回 errors。
EOF
)"
```

---

### Task 3: 前端 WatchlistView

**Files:**
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`

**Interfaces:**
- Consumes: Task 1–2 API
- Produces: ↑↓ + checkbox 批量工具条

- [ ] **Step 1: API 客户端**

```typescript
// watchlist.ts — 类型与方法
export type GroupMembersBatchResult = {
  ok: boolean
  action: 'add' | 'remove'
  added: number
  removed: number
  skipped: number
  errors: Array<{ symbol: string; detail: string }>
}

// in watchlistApi:
reorderGroups: (groupIds: string[]) =>
  api<WatchlistGroup[]>('/api/v1/watchlist/groups/reorder', {
    method: 'PUT',
    body: JSON.stringify({ group_ids: groupIds }),
  }),
batchGroupMembers: (groupId: string, symbols: string[], action: 'add' | 'remove') =>
  api<GroupMembersBatchResult>(
    `/api/v1/watchlist/groups/${encodeURIComponent(groupId)}/members/batch`,
    {
      method: 'POST',
      body: JSON.stringify({ symbols, action }),
    },
  ),
```

- [ ] **Step 2: WatchlistView — 排序**

- `groupIndex` computed：当前 `groupId` 在 `groups` 中的下标  
- `onMoveGroup(delta: -1 | 1)`：交换相邻 → `reorderGroups(groups.map(g => g.id))` → 刷新 groups  
- 模板：`groupId` 非空时按钮「上移」「下移」，边界 `disabled`

- [ ] **Step 3: WatchlistView — 多选批量**

- `checked = ref<Set<string>>(new Set())` 存 `vt_symbol`  
- 表头 checkbox：全选/取消当前 `displayRows`（过滤后可见行）  
- 行 checkbox：`@click.stop` 避免触发行选中冲突（行点击仍可选中详情）  
- `batchTargetGroupId = ref('')`  
- 勾选非空时工具条：目标组 select（`groups.filter(g => g.id !== groupId)`）+「批量加入」；`groupId` 时「批量移出此组」  
- 成功后 `checked.clear()` + `refresh()`；`skipped` 或 `errors.length` 时短提示  

- [ ] **Step 4: build**

```bash
cd frontend && npm run build
```

Expected: exit 0

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/watchlist.ts frontend/src/views/WatchlistView.vue
git commit -m "$(cat <<'EOF'
feat(watchlist): 分组上下排序与批量移组 UI

多选批量加入/移出；分组旁上移下移。
EOF
)"
```

---

### Task 4: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在现有分组条附近增补/改写：

```markdown
- [ ] `/watchlist` 选中分组：可上移/下移，刷新后下拉顺序保持
- [ ] `/watchlist` 列表可多选；可批量加入目标组；分组视图可批量移出此组（不删自选池标的）
```

保留原改名/删组/单行入出组条或合并表述，避免丢验收点。

- [ ] **Step 2: roadmap**

```markdown
28. ~~自选分组排序与批量移组~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-groups-sort-batch-design.md)）
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: `OK：测试与构建通过`

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 记录自选分组排序与批量移组完成

更新 smoke 与路线图 #28。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| §1 reorder | 1 |
| §2 batch | 2 |
| §3 前端 | 3 |
| §4 测试 | 1–2 |
| §5–6 文档/验收 | 4 |
| 不拖拽 / 不删自选 | Global + Task 2–3 |

无 TBD。路由顺序：`groups/reorder` 与 `members/batch` 须避开 path 参数抢占。
