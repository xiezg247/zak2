# 自选持仓与风控 UX 打磨设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；风控 tip + 持仓现价/市值 + 计划外芯片）  
范围：仅 zak2 `WatchlistView` 持仓/风控区；不改后端 board 组装与 CRUD API

## 背景

策略看盘已有持仓录入/改删、风险列、计划外高亮、风控偏好卡片。缺口：风控 tip 仍写「桌面」；持仓表未展示已有 `last_price` / `market_value`；`off_plan_symbols` 未在 UI 暴露为可点列表。

## 目标

1. 风控 tip 改为 zak2 语义（写入用户风控偏好），去掉「桌面」。  
2. 持仓表增加 **现价**、**市值** 列。  
3. 「计划外 N」（N>0）可点展开 `off_plan_symbols` 芯片；点芯片 `selectVt`。  
4. 不改持仓 CRUD / risk tag / strategy_board 计算。

## 非目标

- 计划激活/编辑 UI  
- 持仓表单 `plan_pct` / 后端重排计划外行  
- 录入成功后滚动定位  
- 交易下单、策略引擎

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 |
| 市值格式 | `toLocaleString()`（空 —） |
| 计划外 | 点击切换展开 chips；无则不可点 |
| 录入反馈 | 保持现有 posMsg/posError |

---

## 1. 类型

`frontend/src/api/watchlist.ts` — `StrategyPositionRow` 增加：

```typescript
market_value: number | null
```

（`last_price` 已有。）

## 2. UI 行为

### 2.1 风控 tip

原文含「与桌面同表 trading/risk」→ 改为：

`止损按百分数填写（如 5 = 5%）；浮亏警戒为负数（如 -5）。写入用户风控偏好。`

### 2.2 持仓表列

顺序：代码 · 成本 · 数量 · **现价** · **市值** · 浮盈% · T+1 · 退出 · 风险 · 操作  

| 列 | 数据 | 格式 |
|----|------|------|
| 现价 | `last_price` | `toFixed(2)`，空 — |
| 市值 | `market_value` | `toLocaleString()`，空 — |

空表 `colspan` 随列数调整（10）。

### 2.3 计划外芯片

- 状态：`showOffPlanChips`（boolean，默认 false）  
- `off_plan_count > 0`：「计划外 N」渲染为可点控件；点击 toggle `showOffPlanChips`  
- 展开时：在 risk-summary 下方列出 `riskSummary.off_plan_symbols` chips；点击 → `selectVt(vt)`  
- `count === 0`：纯文本，不可点  
- board 刷新后可保持展开态（不必强制收起）

## 3. 文档

- `docs/smoke-checklist.md`：风控 tip 无桌面；持仓可见现价/市值；计划外可展开选中  
- `docs/product-roadmap.md`：记「持仓与风控 UX 打磨」完成

## 4. 验收

1. 风控 tip 不含「桌面」。  
2. 有行情时持仓行显示现价与市值。  
3. 有计划外时可展开芯片并选中标的。  
4. 持仓改删、风控保存行为不变。  
5. `./scripts/check.sh` 绿。

## 明确不做

后端改动；计划编辑；`plan_pct` 表单；计划外行后端置顶；滚动定位。
