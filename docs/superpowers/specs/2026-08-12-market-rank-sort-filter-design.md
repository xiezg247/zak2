# 市场排行：过滤 + 排序 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；过滤隐藏时保留选中）  
范围：仅 zak2 `MarketView` 排行表区；不改情绪周期/阈值、板块页、ranks API

## 背景

市场排行已有 field tabs（涨幅/换手/成交额/量比/连板）与点行看日 K，但无代码/名称过滤、无表头二次排序，空态未区分「真无排行」与「过滤无匹配」。

## 目标

1. 顶部过滤：按 `vt_symbol` / `name` 子串匹配（忽略大小写）。  
2. 列头可点排序：现价、涨幅%、以及当前 tab 对应分数字段（见下）；「默认序」恢复 API 返回序。  
3. 空态：真无排行 vs 无匹配。  
4. 过滤隐藏当前选中行时 **保留** `selected` 与右侧详情（对齐自选）。

## 非目标

- 改 `/api/v1/market/ranks` 契约或 limit  
- 情绪周期卡片、判定阈值编辑器  
- 市场↔板块联动、列偏好 / localStorage  
- 去掉 field tabs（请求侧排序保留）

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 `displayedRanks` |
| 管道 | `ranks` → filter → sort → 表格 |
| 默认同序 | 清空前端 sort = 当前 field 下 API 序 |
| 过滤掉选中 | 保留 selected / 详情；高亮仅可见行 |
| `#` 列 | `displayedRanks` 的 1-based 可见序号 |

---

## 1. UI 行为

### 1.1 过滤

- 有 `ranks.length` 时显示输入框（placeholder「过滤代码/名称」）与「默认序」。  
- `query` trim 后匹配 `vt_symbol` 或 `name`（大小写不敏感）。

### 1.2 排序

可点列：

| 列 | sort key |
|----|----------|
| 现价 | `last_price` |
| 涨幅% | `change_pct` |
| 换手% / 成交额 / 量比 / 连板 | 仅当当前 `field` 为对应 id 时，表头该动态列可点；key 分别为 `turnover_rate` / `amount` / `volume_ratio` / `limit_times` |

当 `field === 'change_pct'` 时，动态列与「涨幅%」同义，**只**在「涨幅%」列挂排序，动态列不重复挂。

- 同列再点：升 ↔ 降；换列默认降序。  
- 「默认序」：`sortKey = null`。  
- `null` / NaN 垫底（对齐自选）。  
- 成交额展示格式保持现有 `scoreLabel`（亿）。

### 1.3 空态

| 条件 | 展示 |
|------|------|
| `error` | 现有错误文案 |
| `!ranks.length`（非过滤） | 「暂无排行（需 Redis 行情快照）」 |
| `ranks.length && !displayedRanks.length` | 「无匹配标的」；过滤条仍可见 |

加载态沿用现有 toolbar `loading` / 刷新按钮，不强行改轮询。

### 1.4 选中

- `selected` 仍由 `selectRank` 设置；`load` 刷新时按 `vt_symbol` 回填逻辑不变。  
- 过滤后行不可见：不自动清空 `selected`；右侧详情与 K 线仍显示。  
- 行 `:class="{ on: ... }"` 仅当该行在表格中渲染时可见高亮。

### 1.5 数据流

```
ranks (API by field) → filter(query) → sort(key, dir | 默认) → displayedRanks → v-for
```

field tabs / `watch(field)` / 自动刷新 **不变**。切换 field 时前端 filter/sort 可保留（YAGNI 不强制重置）。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/MarketView.vue` | `displayedRanks`、过滤条、表头、空态 |
| `docs/smoke-checklist.md` | `/market` 检查项 |
| `docs/product-roadmap.md` | 近期待办条目 |

---

## 3. 验收

1. `/market` 有排行时可过滤代码/名称、按现价/涨幅/当前分数字段排序、恢复默认序。  
2. 无匹配与真无排行文案可区分。  
3. 过滤掉选中行后右侧详情仍在；tabs 与自动刷新仍可用。  
4. `./scripts/check.sh` 绿。

## 4. 风险

- field tabs（请求序）与表头二次排序并存——靠「默认序」标明恢复请求序。  
- `#` 改为可见序号后，不再直接展示 API `rank` 字段；若用户需要原名次，可后续加列（本刀不做）。
