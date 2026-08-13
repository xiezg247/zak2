# 市场排行空态与日 K Ops 引导 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：纯前端；排行空态去 Ops；日 K loading/空/错三分 + Ops 链）  
范围：仅 zak2 `MarketView`；不改 market / watchlist bars API

## 背景

`/market` 情绪周期无数据时已有「去 Ops」；排行真无数据仅文案「暂无排行（需 Redis 行情快照）」无链接。详情日 K：请求成功但 `bars` 为空时仍显示「加载日 K…」（假加载）；`barsError` 无 Ops 引导。回测 #34 已对日 K 不足做 Ops 链，本刀对齐。

## 目标

1. 排行空态旁挂可点「去 Ops」。  
2. 详情日 K 区分：加载中 / 错误 / 空成功；后两者链「去 Ops 补全日 K」。  
3. 更新 smoke 与路线图 #36。

## 非目标

- 改 `/api/v1/market/*` 或 `watchlist` bars 契约  
- 情绪阈值、排行过滤排序、加自选 / 打开自选逻辑  
- Ops 深链到具体 job、自动触发补数

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端文案 + `RouterLink` |
| 排行空态链文案 | 「去 Ops」（对齐情绪周期） |
| 日 K Ops 链文案 | 「去 Ops 补全日 K」（对齐回测） |
| 空成功 | 非 loading 且无 error 且 `!bars.length` →「暂无日 K」+ Ops 链 |
| loading | 新增 `barsLoading`，避免空成功假「加载中」 |

---

## 1. UI 行为

### 1.1 排行空态

现有：

```vue
<td colspan="6" class="empty">暂无排行（需 Redis 行情快照）</td>
```

改为同单元格内保留原句，并加：

```vue
<RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
```

过滤无匹配「无匹配标的」**不变**（不挂 Ops）。

### 1.2 详情日 K

`selectRank`：

- 开始：`barsLoading = true`，清空 `bars` / `barsError`  
- `finally`：`barsLoading = false`

模板（有 `selected` 时）：

| 条件 | UI |
|------|-----|
| `barsLoading` | 「加载日 K…」 |
| `barsError` | `err` 文案 + `RouterLink`「去 Ops 补全日 K」 |
| `!bars.length` | 「暂无日 K」+ 同上 Ops 链 |
| 有 `bars` | 现有 `CandleChart` |

`onField` 清空选中时同步清 `bars` / `barsError` / `barsLoading`（或仅靠无 `selected` 不渲染）。

### 1.3 样式

复用现有 `.draft-link`；无需新视觉体系。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/MarketView.vue` | `barsLoading`、空态文案、Ops 链 |
| `docs/smoke-checklist.md` | `/market` 验收条 |
| `docs/product-roadmap.md` | #36 |

---

## 3. 验收

1. 无排行时见原空态文案 +「去 Ops」可进 `/ops`。  
2. 选中标的：加载中见「加载日 K…」；失败见错误 +「去 Ops 补全日 K」；成功无 bar 见「暂无日 K」+ 同链（不再假加载）。  
3. 有日 K 时图表行为不变；排行过滤/情绪/互链不变。  
4. smoke + roadmap 已更新。

## 风险

「暂无日 K」与接口瞬时空可能偶发；用户点 Ops 自行判断是否补数，可接受。
