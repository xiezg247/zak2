# 选股 Hub 结果表：行业列 + 排序 + 过滤 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；对齐自选列表思路）  
范围：仅 zak2 `ScreenerHubView` 结果表；不改 screener API / 引擎

## 背景

Hub 结果表列多但无行业展示、无表头排序、无代码/名称过滤。行 dict 已含 `industry`（`screener_repo` pack）；前端 `rows` 为 `Record`，未用。

## 目标

1. 结果表「名称」后增加 **行业** 列。  
2. 数字列表头可排序；默认保持接口返回顺序；空值垫底。  
3. 过滤框：匹配 `vt_symbol` / `symbol` / `name` / `industry`（忽略大小写）。  
4. 未运行 vs 过滤无匹配文案区分。  
5. 自选 / 找同类 / CSV / 历史 / 行业分布行为不变（CSV 与行业分布仍基于完整 `rows`）。

## 非目标

- 批量入自选、列勾选偏好  
- 改后端 schema / 运行逻辑 / 硬过滤 / 权重  
- 结果表虚拟滚动

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 `displayedRows` |
| 得分排序 | 与展示一致的多字段回落 |
| 导出 | 不过滤（完整结果） |
| 清排序 | 「默认序」控件 |

---

## 1. UI 行为

### 1.1 列

在「名称」与「现价」之间插入：

| 列 | 数据 | 格式 |
|----|------|------|
| 行业 | `industry` | trim；空 — |

其余列不变。空行 `colspan`：15 → 16。

### 1.2 排序

可点列：`last_price`、`change_pct`、`turnover_rate`、`volume_ratio`、`score`。

- 同列再点：升 ↔ 降。  
- 「默认序」：清除 sort。  
- `score` 数值：`similarity_score` ?? `pattern_score` ?? `leader_score` ?? `score`（与单元格展示优先级一致）。  
- `null` / 非数字：比较时垫底（升序、降序均末尾）。

### 1.3 过滤

- 结果区上方 input，placeholder：`过滤代码/名称/行业`。  
- `query` trim 后，保留任一字段子串匹配（大小写不敏感）。  
- 先 filter 再 sort。

### 1.4 空态

| 条件 | 文案 |
|------|------|
| `rows.length === 0` | `运行选股后在此显示结果` |
| 有 rows 但 `displayedRows` 空 | `无匹配结果` |

### 1.5 数据流

```
rows (current.result.rows) → filter(query) → sort(key, dir) → 表格 v-for displayedRows
```

`industry_dist` / `diff` / `exportCsv` 仍用完整 `rows`。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/ScreenerHubView.vue` | displayedRows、过滤、排序、行业列、空态 |
| `docs/smoke-checklist.md` | Hub 结果表检查项 |
| `docs/product-roadmap.md` | 完成项 |

---

## 3. 验收

1. 有行业字段时结果表可见行业列。  
2. 点涨幅等可排序；过滤后排序作用于子集。  
3. 空态文案区分未运行 / 无匹配。  
4. 导出 CSV 仍为完整结果；自选/找同类正常。  
5. `./scripts/check.sh` 绿。

## 明确不做

后端改动；批量入自选；列偏好；虚拟滚动。
