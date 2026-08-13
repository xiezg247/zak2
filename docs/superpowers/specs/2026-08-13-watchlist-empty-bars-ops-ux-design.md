# 自选列表空态与日 K Ops 引导 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：列表空态文案；barsLoading + 空/错去 Ops 补全日 K）  
范围：仅 zak2 `WatchlistView` 列表区与详情日 K；不改 watchlist API / 分组 / 策略看盘

## 背景

自选列表空态为「自选为空…」/「无匹配结果」，与笔记/市场「暂无…／无匹配…」不一致。详情日 K：`loadBars` 无 `barsLoading`；空成功时无提示；`barsError` 无 Ops 链。市场 #36 已对齐日 K Ops 引导。

## 目标

1. 列表区分暂无自选 / 无匹配标的（文案打磨）。  
2. 详情日 K 区分加载 / 空 / 错；空与错链「去 Ops 补全日 K」。  
3. 更新 smoke 与路线图 #41。

## 非目标

- 改 `/api/v1/watchlist*` 契约  
- 空自选挂 Ops、行业空 Ops、分组/列偏好/策略看盘  
- 批量补全日 K UI

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 |
| 暂无 | 「暂无自选标的，上方输入代码添加」（不挂 Ops） |
| 无匹配 | 「无匹配标的」 |
| 日 K Ops 文案 | 「去 Ops 补全日 K」（对齐市场） |
| loading | `barsLoading` |

---

## 1. UI 行为

### 1.1 列表空态

现有表内空行：

```vue
{{ items.length === 0 ? '自选为空，上方输入代码添加' : '无匹配结果' }}
```

改为：

```vue
{{ items.length === 0 ? '暂无自选标的，上方输入代码添加' : '无匹配标的' }}
```

顶部「刷新中…」保留；过滤框仅在有数据时的现行为不变（若过滤框始终可见亦可，不强制改）。

### 1.2 详情日 K

`loadBars`：

- 开始：`barsLoading = true`，清 `bars` / `barsError`  
- `finally`：`barsLoading = false`  
- 无 `selected` 时直接 return（loading 仍须复位）

模板（有 `selected`）：

| 条件 | UI |
|------|-----|
| `barsLoading` | 「加载日 K…」 |
| `barsError` | `err` + `RouterLink`「去 Ops 补全日 K」 |
| `!bars.length` | 「暂无日 K」+ 同上 |
| 有 bars | 现有图表与迷你表 |

无 `selected`：仍「选择左侧标的查看日 K」。

样式：补 `.draft-link`（若无）。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/WatchlistView.vue` | 文案、`barsLoading`、Ops 链 |
| `docs/smoke-checklist.md` | `/watchlist` 验收 |
| `docs/product-roadmap.md` | #41 |

---

## 3. 验收

1. 无自选见「暂无自选标的…」；过滤无匹配见「无匹配标的」。  
2. 选中后：加载中见「加载日 K…」；失败或空成功见 Ops 链；有日 K 图表不变。  
3. 分组/列/策略看盘不变。  
4. smoke + roadmap 已更新。

## 风险

无；纯前端。
