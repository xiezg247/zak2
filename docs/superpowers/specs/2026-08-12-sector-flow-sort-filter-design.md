# 板块资金表：过滤 + 排序 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；不改后端）  
范围：仅 zak2 `SectorView`；不改市场页 / 雷达 / Ops sync 逻辑

## 背景

板块资金页已有概念/行业、交易日、请求侧「净流入|涨幅」排序与表格，但无名称/ID 过滤、无表头二次排序、空态未区分「真无数据」与「过滤无匹配」。

## 目标

1. 顶部过滤：按 `name` / `sector_id` 子串匹配（忽略大小写）。  
2. 列头可点排序：涨幅%、净流入(亿)；提供「默认序」恢复接口返回顺序。  
3. 空态三分：加载中 / 真无数据 / 无匹配。  
4. toolbar（kind / tradeDate / 请求 sort）行为不变。

## 非目标

- 成分股下钻、新 API、改 `sectorFlow` 契约  
- 市场页联动、列勾选偏好 / localStorage  
- 改 AI / 雷达 / Ops job 实现（空态可文案提示去 Ops，不新做同步 UI）

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 `displayedRows` |
| 管道 | `rows` → filter → sort → 表格 |
| 默认同序 | 清空前端 sort = 当前 API 返回序（仍尊重 toolbar 请求 sort） |
| 空值排序 | null/缺省垫底（对齐自选列表） |
| 交互深度 | 表内打磨 only；不点行下钻 |

---

## 1. UI 行为

### 1.1 过滤

- 有 `rows.length` 时显示输入框（placeholder 如「过滤名称/ID」）与「默认序」。  
- `query` trim 后，保留 `name` 或 `sector_id` 包含 query（大小写不敏感）的行。

### 1.2 排序

- 可点列：`change_pct`、`net_flow_yi`（表头 ▲/▼）。  
- 同列再点：升 ↔ 降；换列时默认降序（与自选/雷达一致）。  
- 「默认序」：`sortKey = null`，展示过滤后的接口顺序。  
- `#` 列为 `displayedRows` 的 1-based 序号。

### 1.3 空态

| 条件 | 展示 |
|------|------|
| `loading` | 「加载中…」 |
| `!loading && !error && !rows.length` | 「暂无板块资金」（可一句提示 Ops 同步 `sync_sector_flow_daily`） |
| `rows.length && !displayedRows.length` | 「无匹配板块」；过滤条仍可见 |

错误态保持现有 `error` 文案。

### 1.4 数据流

```
rows (API) → filter(query) → sort(key, dir | 默认) → displayedRows → v-for
```

`kind` / `sort` / `tradeDate` 的 `watch` → `loadFlow` 不变；切换条件时前端 filter/sort 状态可保留（不过度重置，YAGNI）。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/SectorView.vue` | 状态、`displayedRows`、表头、空态、样式 |
| `docs/smoke-checklist.md` | `/sectors` 检查项 |
| `docs/product-roadmap.md` | 近期待办条目 |

---

## 3. 验收

1. `/sectors` 有数据时可过滤名称/ID、按涨幅/净流入排序、恢复默认序。  
2. 无匹配与真无数据文案可区分。  
3. 概念/行业、日期、请求侧排序仍可用。  
4. `./scripts/check.sh` 绿。

## 4. 风险

- 前端二次排序与 toolbar「净流入|涨幅」并存时，用户可能混淆「请求序」与「表头序」——用「默认序」文案标明恢复请求返回序即可。  
- 无成分 API，用户点行无下钻属预期（非目标）。
