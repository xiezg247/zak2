# 自选 · 当日计划对照卡设计

日期：2026-08-07  
状态：已批准（方案 A：扩 strategy-board.risk_summary + 自选 UI）  
范围：仅 zak2；只读；不改 zak；无计划 CRUD / 下单

## 目标

在自选策略区展示当日 `status=active` 交易计划标的，并标明相对自选/持仓的三态，便于与「计划外」对照。

## 非目标

- 计划创建/编辑/删除、从计划加自选、下单  
- 守则页大改、独立 `/plans` 路由  
- 改 zak / vnpy-*

## API（扩 `GET /api/v1/watchlist/strategy-board`）

`risk_summary` 增加：

```json
"plan_symbols": [
  {
    "vt_symbol": "600519.SSE",
    "name": "茅台",
    "in_watchlist": true,
    "in_position": false
  }
]
```

组装规则：

- 计划来源：现有 `load_active_plan_snapshot(db, user_id, trade_date)`  
- 无计划：`plan_symbols: []`（`active_plan_date` 仍为 `""`）  
- 顺序：计划 symbols 的 `sort_order`  
- `in_watchlist`：`vt_symbol` ∈ 当前用户自选  
- `in_position`：`vt_symbol` ∈ 本 board `positions`  
- `name`：优先自选 `name`，否则 `""`  

Schema：`RiskSummaryOut` 增加 `plan_symbols: list[PlanSymbolStatus]`；  
`PlanSymbolStatus`：`vt_symbol, name, in_watchlist, in_position`。

既有字段（`off_plan_*`、`plan_max_pct` 等）不变。

## 前端（WatchlistView）

- 位置：策略区风控卡片下方（通知历史附近）  
- 块标题：「当日计划」+ `risk_summary.active_plan_date`  
- 无计划 / 空列表：空态文案「当日无 active 计划」  
- 有数据：列表行  
  - 可点击 `vt_symbol` → 现有 `selectVt`  
  - 标签优先：`in_position` →「持仓」；else `in_watchlist` →「自选」；else「仅计划」  
- 只读；无加自选按钮  
- 类型：`RiskSummary` 增加 `plan_symbols`

## 测试

- board：有计划时 `plan_symbols` 三态正确（mock snapshot + watchlist + positions）  
- 无计划 → `[]`  
- 不打真网  

## 文档

- gap：守则/计划只读 → 自选可见当日计划对照  
- smoke：自选可见计划标的三态  

## 验收

1. active 计划标的列表与三态正确  
2. 无计划空态；点击可选中  
3. pytest + `npm run build` 绿  
