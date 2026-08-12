# 自选列表：扩列 + 排序 + 过滤 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；不改后端 schema）  
范围：仅 zak2 `WatchlistView` 列表区；不改策略看盘/持仓/分组 CRUD

## 背景

自选列表仅展示代码 / 名称 / 行业 / 现价 / 涨幅%。`WatchlistItemOut` 已含 `turnover_rate` / `volume_ratio` / `amount` 等，前端未用；无表头排序、无代码/名称过滤。

## 目标

1. 默认扩列：**换手%**、**量比**、**成交额**（另保留代码/名称/行业/现价/涨幅%/删）。  
2. 数字列表头可点排序（升/降）；默认保持接口返回的 `sort_order` 顺序。  
3. 顶部过滤框：按 `vt_symbol` / `name` 子串匹配（忽略大小写）。  
4. 选中行、日 K、删除自选行为不变。

## 非目标

- 列勾选偏好 / localStorage  
- 扩展后端字段（振幅、净流入、市值等）  
- 涨跌闪烁动画、分组管理增强、策略看盘改版  
- 改 AI / Ops

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 |
| 成交额格式 | `amount/1e8` → `x.xx亿`（对齐市场页） |
| 空值排序 | 统一排在末尾 |
| 清排序 | 提供「默认序」控件清空 sort |

---

## 1. UI 行为

### 1.1 列

| 列 | 数据 | 格式 |
|----|------|------|
| 代码 | `vt_symbol` | mono |
| 名称 | `name` | 空 — |
| 行业 | `industry` | trim 空 — |
| 现价 | `last_price` | `toFixed(2)` |
| 涨幅% | `change_pct` | `toFixed(2)` + 红绿 class |
| 换手% | `turnover_rate` | `toFixed(2)` |
| 量比 | `volume_ratio` | `toFixed(2)` |
| 成交额 | `amount` | `/1e8` → `x.xx亿` |
| 删 | 按钮 | 不变 |

### 1.2 排序

- 可点列：`last_price`、`change_pct`、`turnover_rate`、`volume_ratio`、`amount`（表头带指示 ▲/▼ 或文案）。  
- 同列再点：升 ↔ 降。  
- 「默认序」：清除 sort，恢复接口顺序（再经过滤）。  
- `null` / 缺行情：比较时视为「最大」使得升序在末、降序也在末（即始终垫底）。

### 1.3 过滤

- 输入框 placeholder 如「过滤代码/名称」。  
- `query` trim 后，保留 `vt_symbol` 或 `name` 包含 query（大小写不敏感）的行。  
- 过滤作用于展示列表；排序在过滤后的子集上进行。

### 1.4 数据流

```
items (API) → filter(query) → sort(key, dir) → 表格 v-for
```

用 `computed` 派生 `displayedItems`；`selected` 仍基于原 `items` 查找（过滤隐藏时若已选中可保留选中态，或仍显示 chart——推荐**保留选中**，即使当前过滤不可见）。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/WatchlistView.vue` | 列、过滤、排序、displayedItems、样式微调 |
| `docs/smoke-checklist.md` | 自选列表检查项 |
| `docs/product-roadmap.md` | 可选完成记录 |

不改 `frontend/src/api/watchlist.ts`（类型已够）；不改 backend。

---

## 3. 验收

1. 默认可见换手 / 量比 / 成交额列。  
2. 点涨幅表头可排序；再点切换方向；「默认序」恢复。  
3. 过滤「600」等可缩小列表；与排序叠加正确。  
4. 空行情显示 —，无 `NaN`。  
5. 选中 / 日 K / 删除仍正常。  
6. `frontend` build（`./scripts/check.sh` 或至少 `npm run build`）通过。

## 明确不做（复述）

列偏好；后端扩字段；分组 CRUD；策略看盘；闪烁动画。
