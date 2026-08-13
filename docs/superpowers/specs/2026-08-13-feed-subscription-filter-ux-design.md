# Feed 左侧订阅过滤 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：纯前端；display_name + source_id；保持 subId）  
范围：仅 zak2 `FeedView`；不改 Feed API / 批量已读 / 页内强制同步

## 背景

`/feed` 已有订阅管理、时间线刷新，以及 #23 右侧标题/作者/摘要过滤与「仅未读」。左侧订阅列表无过滤；订阅多时难定位。#23 非目标含「订阅名过滤」——本刀补齐，与笔记侧栏 #31、回测历史 #33 一致。

## 目标

1. 左侧按订阅显示名 / mid（`source_id`）过滤。  
2. 「全部」始终可见；无匹配时空态「无匹配订阅」。  
3. 滤掉当前订阅时保持 `subId`，右侧仍按该订阅展示。  
4. 更新 smoke 与路线图 #35。

## 非目标

- 改 `/api/v1` Feed 契约或服务端搜索  
- 批量已读、页内强制同步、「仅启用」过滤  
- 改右侧 `listFilter` / `unreadOnly`（#23 已有）  
- 过滤时自动清空 `subId`

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 `displayedSubs` |
| 匹配 | `display_name` + `source_id`（trim，大小写不敏感） |
| 过滤框可见 | `subs.length > 0` |
| 「全部」 | 始终显示，不参与过滤匹配 |
| 选中被滤掉 | 保持 `subId`；右侧时间线仍按该订阅 |

---

## 1. UI 行为

### 1.1 过滤

- 订阅列表上方（「全部」之前）：`<input>`，`subs.length > 0` 时显示；placeholder「过滤订阅名/mid」。  
- `subFilter` → `displayedSubs`：对 `display_name`、`source_id` 做 includes 匹配。  
- 「全部」按钮始终保留；`v-for` 用 `displayedSubs`（含开/关/删行）。

### 1.2 数据流

```
subs (API) → text filter(subFilter) → displayedSubs → 左侧列表
subId 不变 → feedItems(subId) / 右侧 displayedItems（#23）不变
```

添加 / 搜索 UP / 开关删 / 刷新 / 右侧过滤 **不变**。

### 1.3 空态

| 条件 | 左侧订阅区 | 右侧 |
|------|------------|------|
| `loading` | （现有全页「加载中…」在右侧；左侧可保持现结构） | 「加载中…」 |
| `!subs.length` | mid/搜索引导 +「全部」；无订阅行 | 「暂无订阅」等现有 |
| `subs.length && !displayedSubs.length` | 过滤框 +「全部」+「无匹配订阅」 | 仍按 `subId` 显示时间线（含被滤掉的选中） |
| 有匹配 | 过滤框 +「全部」+ 匹配行 | 现有 |

错误态保持现有 `error` 行。

### 1.4 与 #23 关系

右侧 `listFilter` / `unreadOnly` / `displayedItems` 不动。本刀只增左侧 `subFilter` / `displayedSubs`。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/FeedView.vue` | `subFilter`、`displayedSubs`、空态文案、样式 |
| `docs/smoke-checklist.md` | `/feed` 左侧订阅过滤与空态验收 |
| `docs/product-roadmap.md` | 近期待办完成项 #35 |

---

## 3. 验收

1. 有订阅时可按名/mid 过滤；无匹配见「无匹配订阅」；「全部」仍可见。  
2. 过滤隐藏当前选中订阅时，右侧时间线仍按该 `subId`（不强制清选中）。  
3. 无订阅时不显示订阅过滤框；现有添加引导不变。  
4. 右侧时间线过滤（#23）行为不变。  
5. smoke + roadmap 已更新。

## 风险

订阅数量通常不大，纯前端过滤足够；若未来上千条再考虑服务端。
