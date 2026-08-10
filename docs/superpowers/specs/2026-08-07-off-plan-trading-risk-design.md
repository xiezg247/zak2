# 计划外 + trading/risk 偏好（自选薄刀）设计

日期：2026-08-07  
状态：已批准（方案 1：扩 strategy-board + 独立 trading-risk API）  
范围：仅 zak2；不改 zak / vnpy-*；共用 PG `auth.user_preferences` 与 `trading_plans`

## 目标

1. **计划外只读**：相对用户当日 `status=active` 交易计划观察名单，标记不在名单内的持仓；策略看盘展示。
2. **trading/risk 偏好**：读/写 `auth.user_preferences`（`namespace=trading`, `key=risk`，与桌面同表）；自选页卡片可改总资金、止损%、浮亏警戒；展示 `sum(持仓市值)/total_capital` 实际仓位占比。

## 非目标

- 通知历史 / 飞书 / API 内异动扫描
- 开盘止损、隔日退出、计划 CRUD（计划仍只读）
- 下单、TickFlow 进 API

## 计划外算法

- 交易日：优先传入/使用最近开市日（与现有日历工具一致）；格式 `YYYY-MM-DD`。
- 加载该用户该日 `trading_plans` 中 `status=active` 按 `updated_at` 最新一条；无则 **全部非计划外**。
- 计划标的集合 = 对应 `trading_plan_symbols` 的 `(symbol, exchange)`（比较时规范化为 `vt_symbol`）。
- 持仓 `vt_symbol` 不在集合 → `off_plan=true`。
- `risk_tags` 增加「计划外」；排序插入为：  
  `卖出信号` > **`计划外`** > `急跌` > `浮亏` > `放量` > `大涨` > `浮盈`  
  （更新 `position_risk_tags.TAG_ORDER` 与 `compute_position_risk_tags` 增加 `off_plan: bool` 参数。）

## 仓位占比

- `actual_mv = sum(持仓行 market_value)`（无价则该行不计或 0）
- `actual_position_pct = actual_mv / total_capital`（`total_capital` 缺失或 ≤0 → `null`）
- 若有 active 计划：暴露 `plan_max_pct`。约定：**与桌面/表字段一致，按 0–1 小数存储**（如 0.3=30%）；若读到值 `>1` 则视为百分数并 `/100` 再返回（防御脏数据）。

## Risk prefs

存取 `auth.user_preferences`：

| 字段 | 默认 | 校验 |
|------|------|------|
| `total_capital` | null | null 或 >0 |
| `stop_loss_pct` | 0.05 | (0, 0.5] |
| `caution_float_pct` | -5.0 | <0 |
| `realized_pnl_today` | null | 本刀 GET 带回；PUT 可忽略或透传 |

`normalized()` 规则对齐桌面 `TradingRiskPrefs.normalized`。

## API

### `GET/PUT /api/v1/watchlist/trading-risk`

- GET → 当前用户 prefs（normalized）+ 可选只读汇总字段可放 board
- PUT body 同上核心三字段（+ 可选 realized）；非法 → 400 中文

### `GET /api/v1/watchlist/strategy-board`（扩展）

持仓行增加：

- `off_plan: bool`
- `risk_tags` 可含「计划外」

顶层增加 `risk_summary`：

```json
{
  "total_capital": 100000,
  "actual_position_pct": 0.12,
  "plan_max_pct": 0.3,
  "off_plan_count": 1,
  "off_plan_symbols": ["600519.SSE"],
  "active_plan_date": "2024-08-05"
}
```

无计划时：`active_plan_date=""`，`off_plan_count=0`，`plan_max_pct=null`。

## 前端（自选 · 策略看盘上方）

- 卡片：总资金 / 止损% / 浮亏警戒 + 保存；展示仓位占比、计划外数量、active 计划日
- 持仓表：`off_plan` 高亮或风险列含「计划外」
- 不改计划编辑（仍守则/信息流只读）

## 错误与降级

| 情况 | 行为 |
|------|------|
| 无 active 计划 | 全部非计划外 |
| 无总资金 | 占比 null，UI「—」 |
| prefs 缺失 | 默认值 |
| PUT 非法 | 400 |

## 测试

- off_plan 差集 / 无计划
- prefs normalize 与 PUT 校验
- board `off_plan` + `risk_summary`
- 不打真网

## 文档

- gap：风控薄 → 计划外 + risk 偏好；下一刀可写通知历史
- smoke：自选可见计划外与仓位占比卡片

## 验收

1. active 计划外持仓显示「计划外」  
2. 保存总资金后可见仓位占比；刷新仍在  
3. pytest + `npm run build` 绿  
