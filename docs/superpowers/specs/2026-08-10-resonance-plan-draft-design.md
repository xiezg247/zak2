# 情绪+共振 → 次日交易计划草案设计

日期：2026-08-10  
状态：已批准（方案 1：专用 POST + 只写 draft）  
范围：仅 zak2；不改 zak；无下单；B（`sync_stock_industry`）另刀

## 目标

1. 雷达一键：用当前情绪周期 + 用户加权共振 TopN，写入次日 `trading_plans` **draft**  
2. 同用户同 `trade_date` 的既有 draft **覆盖**；绝不改 `active`

## 非目标

- 计划激活 / 编辑 UI / 确认卡  
- Hub 入口、改共振权重、独立 screener recipe  
- 下单、改 zak  
- Web `sync_stock_industry`（排队下一刀）

## 后端

### Endpoint

`POST /api/v1/radar/plan-draft`（登录）

Body（均可选）：

- `top_n`：默认 5，夹逼 3–8  
- `trade_date`：`YYYYMMDD`；缺省=下一交易日  

### Service

`plan_draft.create_resonance_plan_draft(db, user_id, *, top_n, trade_date=None) -> dict`

1. `build_emotion_cycle(db)`；`stage in {ice, recession}` → HTTP 400「当前情绪不宜新开（冰点/退潮）」；**不写库**  
2. `list_radar_cards` 空 → 400「暂无雷达卡片，请先打开雷达页刷新」  
3. `list_radar_resonance(db, user_id=..., min_cards=2, top_n=top_n)`；entries 空 → 400「暂无共振标的」  
4. 解析 `trade_date`：若未传，取 `app.trade_calendar` 中 `cal_date > today` 且 `is_open` 的最近一日；无则 fallback `latest_open_yyyymmdd(db)`，notes 加「日历缺省用最近开市日」类说明  
5. Upsert draft：  
   - 查同 `user_id` + `trade_date` + `status=draft`（取最新一条）  
   - 有则删其 `trading_plan_symbols` 后重写字段；无则新建 `TradingPlan`（新 id）  
   - **不**修改任何 `active` 行  
6. 字段：  
   - `emotion_expected`：stage 或 stage_label（稳定用 stage id，如 `divergence`）  
   - `max_position_pct`：`load_trading_risk_prefs` 的上限（已有 normalize）；缺省 0.3  
   - `notes`：`雷达共振草案 · 情绪{label} · top_n=N`（+ 可选日历 fallback 备注）  
   - 每标的：`symbol/exchange` 自 vt；`entry_conditions`=`共振 加权{score}：{卡标题}`；`allowed_modes`/`exit_conditions` 空；`sort_order` 按共振序  
7. 返回：`plan_id, trade_date, status="draft", emotion_expected, symbol_count, symbols[{vt_symbol,name}], replaced: bool`

### API 挂载

`market.py`（或 plans 路由若已有）注册上述 POST；鉴权同雷达其它接口。

## 前端

### RadarView

- 按钮「生成次日计划草案」  
- 成功 toast/文案：`已写入 draft · {trade_date} · {n} 只`；链接「去守则看计划」→ `/playbook`  
- 失败展示 `detail`；请求中禁用按钮  

### Playbook

- 不改；只读列表刷新可见 draft  

## 测试

- 冰点/退潮 → 400、无 INSERT  
- 无卡 / 空共振 → 400  
- 有 entries → draft；二次调用 `replaced=true`  
- 存在同日 `active` 时生成 draft **不改** active  
- mock 日历 / 共振；不打真网  

## 文档

- gap：可生成次日 draft；仍无激活/编辑；B 仍另定  
- smoke：雷达按钮写 draft；冰点失败文案明确  

## 验收

1. 有共振时点按钮 → Playbook 见 draft  
2. 同日再点 → 覆盖 draft  
3. pytest + `npm run build` 绿  

## 后续

- **B**：Web 可跑 `sync_stock_industry`（A 验收后再开 brainstorm）
