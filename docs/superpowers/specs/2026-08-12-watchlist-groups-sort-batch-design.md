# 自选分组排序与批量移组设计

日期：2026-08-12  
状态：已批准（方案 A：groups reorder + members/batch；UI 上下箭头 + 多选）  
范围：仅 zak2 自选分组；不引入拖拽、不删自选池标的

## 背景

分组管理闭环已支持建组/改名/删组与单行入出组。分组有 `sort_order` 但无重排 API；列表无多选，无法批量加入/移出。标的侧已有 `PUT /watchlist/reorder` 可对齐。

## 目标

1. 分组 **上移/下移** 调整 `sort_order`，下拉顺序持久。  
2. 列表 **多选**；**批量加入目标组**（「全部自选」与分组视图均可）；分组视图 **批量移出此组**。  
3. 后端：`PUT /watchlist/groups/reorder` + `POST .../groups/{id}/members/batch`；前端接线；测试 + smoke + roadmap **#28**。

## 非目标

- 拖拽排序  
- 「换组」原子操作（出 A 入 B 一次完成）  
- 批量操作时删除自选池标的  
- 策略看盘 / 持仓区  
- 改 zak / vnpy-*

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：独立 reorder + batch 端点 |
| 排序 UI | 上移/下移（非拖拽） |
| 批量 UX | 多选 + 目标组；分组视图另有批量移出 |
| 部分失败 | 其余继续；返回 skipped/errors 摘要 |

---

## 1. 后端：分组重排

### 1.1 Schema

```python
class GroupsReorderRequest(BaseModel):
    group_ids: list[str] = Field(min_length=1, description="分组 id 期望顺序")
```

### 1.2 `reorder_groups(db, user_id, group_ids) -> list[WatchlistGroup]`

对齐 `reorder_items`：

1. 加载用户全部组；按 `group_ids` 排列已知 id（去重）；未出现的组接到末尾。  
2. 写回 `sort_order = index`；commit。  
3. 返回按新顺序的组列表。  

空 `group_ids` → 400（由 schema `min_length=1` 或显式校验）。

### 1.3 路由

`PUT /api/v1/watchlist/groups/reorder` → `list[GroupOut]`

---

## 2. 后端：批量成员

### 2.1 Schema

```python
class GroupMembersBatchRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=100, description="vt_symbol 或灵活代码")
    action: Literal["add", "remove"]
```

### 2.2 `batch_group_members(db, user_id, group_id, symbols, action) -> dict`

- 分组不存在 → 404。  
- **add**：解析每个 symbol；不在自选池 → 记入 `errors`；已在组内 → `skipped++`；否则插入成员。  
- **remove**：解析；成员不存在 → `skipped++`；否则删除成员关系（**不**删 `watchlist` 行）。  
- 一次 `commit`。  
- 返回：

```text
{
  ok: true,
  action: "add" | "remove",
  added?: int,   # action=add
  removed?: int, # action=remove
  skipped: int,
  errors: list[{symbol, detail}]  # 可空
}
```

### 2.3 路由

`POST /api/v1/watchlist/groups/{group_id}/members/batch`

---

## 3. 前端

### 3.1 API（`watchlist.ts`）

- `reorderGroups(groupIds: string[])` → PUT  
- `batchGroupMembers(groupId, { symbols, action })` → POST  

### 3.2 分组排序 UI（`WatchlistView.vue`）

- `groupId` 非空时：改名/删组旁 **上移 / 下移**。  
- 在 `groups` 数组中与相邻项交换 → 全量 id 列表调 `reorderGroups` → 刷新 groups，保持选中。  
- 首项禁用上移、末项禁用下移。

### 3.3 批量移组 UI

- 表格首列 checkbox（表头全选当前**可见**过滤行 + 行选）。  
- 勾选非空时工具条：  
  - **批量加入**：目标组 `<select>`（可排除当前 `groupId`）+ 执行 → `action: "add"`。  
  - 若 `groupId` 非空：**批量移出此组** → `action: "remove"`。  
- 成功后清空勾选、`refresh()`；若有 `errors`/`skipped`，短提示摘要。  
- 保留现有单行「加入/移出此组」。

---

## 4. 测试

| 范围 | 要点 |
|------|------|
| `reorder_groups` | 顺序变更；无效 id 忽略；末尾补齐 |
| `batch` add | 成功计数；未在自选 → errors；已在组 → skipped |
| `batch` remove | 成功计数；不存在 → skipped；自选池行仍在 |
| API（可选） | 404 分组；空 body 422 |

---

## 5. 文档

- `docs/smoke-checklist.md`：分组 ↑↓；多选批量加入/移出。  
- `docs/product-roadmap.md`：**#28** 完成项，链本 spec。

---

## 6. 验收

1. 分组顺序持久，刷新后下拉一致。  
2. 「全部自选」与分组视图均可批量加入；分组视图可批量移出。  
3. 移组不删自选池标的；`./scripts/check.sh` 绿。

## 明确不做（复述）

拖拽；原子换组；删自选池；策略/持仓；zak / vnpy-*。
