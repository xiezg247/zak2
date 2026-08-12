# 自选分组管理闭环设计

日期：2026-08-12  
状态：已批准（方案 A：PATCH 改名 + 补齐删组/入出组 UI）  
范围：仅 zak2 自选分组；不做分组排序拖拽、不做策略看盘

## 背景

后端已有建组、删组、加/移成员；前端 API 已有 `deleteGroup` / `addToGroup`，但 UI 仅「建组 + 下拉筛选」。缺改名（无 PATCH）、删组入口、行级入组/出组。

## 目标

1. 新增 `PATCH /api/v1/watchlist/groups/{group_id}` 改名。  
2. UI：当前选中分组可改名、删除（confirm；删后回「全部自选」）。  
3. UI：仅当 `groupId` 非空且已选中列表行时，可「加入此组」「移出此组」。  
4. 删组只删分组与成员关系，不删自选池标的（现有 `delete_group` 行为）。

## 非目标

- 分组拖拽/上下排序  
- 批量多选移组  
- 「全部自选」下选目标组入组  
- 策略看盘 / 持仓区

## 决策摘要

| 项 | 选择 |
|----|------|
| 改名 | PATCH + `rename_group` |
| 入出组入口 | 仅分组筛选视图 + 已选中行 |
| 删组确认 | `window.confirm` |

---

## 1. 后端

### 1.1 Schema

```python
class GroupRename(BaseModel):
    name: str = Field(min_length=1, max_length=40)
```

（与 `GroupCreate` 约束一致。）

### 1.2 `rename_group(db, user_id, group_id, name) -> WatchlistGroup`

- `name = name.strip()`；空 → 400「分组名不能为空」  
- 分组不存在 → 404  
- 其它组同名（大小写不敏感，排除自身）→ 409「分组名已存在」  
- 更新 `name`，commit，refresh，返回 row  

### 1.3 路由

`PATCH /api/v1/watchlist/groups/{group_id}` → `GroupOut`

### 1.4 测试

新建或扩展 `backend/tests/test_watchlist_groups.py`（mock Session 或现有测试风格）：

- 成功改名  
- 空名 400  
- 重名 409  
- 不存在 404  

---

## 2. 前端

### 2.1 `watchlist.ts`

- `renameGroup(id, name)` → PATCH  
- `removeFromGroup(groupId, vtSymbol)` → DELETE `.../members/{vt}`（后端已有）  
- 接线已有 `deleteGroup` / `addToGroup`

### 2.2 `WatchlistView.vue` 分组区

当 `groupId` 非空：

- **改名**：prompt 或小型 input+确认；调用 `renameGroup`；成功后 refresh groups，保持 `groupId`  
- **删组**：`confirm('确定删除该分组？自选标的不会被删除')` → `deleteGroup` → `groupId=''` → refresh  

当 `groupId` 非空且 `selected` 非空：

- **加入此组**：`addToGroup(groupId, selected.vt_symbol)`；失败展示 error（如未在自选——正常路径已在自选）  
- **移出此组**：`removeFromGroup`；成功 refresh（该行从当前筛选列表消失）  

「全部自选」：不显示入组/出组/改名/删组（或仅隐藏入出组；改名删组本就依赖选中组）。

---

## 3. 文档与验收

| 文档 | 内容 |
|------|------|
| `smoke-checklist.md` | 改名、删组、入组、出组 |
| `product-roadmap.md` | 完成项 + spec 链接 |

**验收**

1. PATCH 单测：成功 / 空 / 重名 / 404。  
2. UI 闭环可用；删组不删自选。  
3. `./scripts/check.sh` 通过。

## 明确不做（复述）

分组排序；批量移组；全部视图下选目标组；策略看盘。
