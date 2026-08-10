# 共振编排加深（Hub 雷达共振 + 卡片 ★）设计

日期：2026-08-10  
状态：已批准（方案 1：builtin recipe + 前端角标）  
范围：仅 zak2；不改 zak；无计划草案

## 目标

1. Hub 内置配方 **雷达共振**：跨卡共振结果写入 `screener_runs`  
2. Radar 明细对出现在 ≥2 张卡的标的显示 ★  

## 非目标

- 情绪+共振 → 交易计划草案  
- 改共振权重算法 / 独立 `POST /runs/resonance`  
- 改 card API 强绑 `card_count`  
- 改 zak / vnpy-*

## 后端

### Builtin

`presets.BUILTIN_RECIPES` 增加：

- `recipe_id`: `radar_resonance`  
- `name`: `雷达共振`  
- `trigger_kind`: `intraday`  
- `top_n`: `20`  
- `implemented`: `True`

### 执行

`engine.run_recipe_screen`：若 `recipe_id == radar_resonance`，转调  
`resonance_screen.run_resonance_screen(db, user_id, top_n, hard_filter, previous_symbols)`。

`run_resonance_screen`：

1. `list_radar_cards(db)`；空 → HTTP 400「暂无雷达卡片，请先打开雷达页刷新」  
2. `load_user_weights(db, user_id)` + `list_radar_resonance(..., weights, top_n, min_cards=2)`  
3. entries 空 → 成功返回空 rows（`condition` 含「暂无共振」类说明）  
4. 映射 row：`vt_symbol, name, change_pct, last_price, score=resonance_score`；`hit_reason` 如 `共振 加权x.x：卡A、卡B`；保留 `seal_time_label`  
5. `_pack_result`：`condition=雷达共振`，`source=radar_resonance`，config 含 `top_n/min_cards`

硬过滤：共振路径可对映射后的 quote 行做可选硬过滤；若实现成本高，本刀允许跳过硬过滤（文档注明），优先保证落库与分数正确。

## 前端

### ScreenerHub

- 配方下拉出现「雷达共振」  
- 跑 `POST /runs/recipe` + `recipe_id=radar_resonance`  
- 无 leader variant 控件  

### RadarView

- 工具栏增加「共振选股 → Hub」→ `/screener?recipe=radar_resonance`  
- 用 `resonance.entries` 建 `vt → card_count`  
- 明细表标的列：可解析 vt 且 `count≥2` 时显示 ★（复用侧栏 `.star`）  

## 测试

- 无卡片 → 400  
- 有 entries → rows/score/condition  
- 空 entries → 成功空结果  
- builtin 含 `radar_resonance`  
- 不打真网  

## 文档

- gap：共振侧栏 → Hub 雷达共振落历史 + 卡片 ★；仍无计划草案  
- smoke：Hub 可跑雷达共振；Radar 明细多卡 ★；「共振选股 → Hub」可用  

## 验收

1. Hub 跑「雷达共振」可落历史  
2. Radar 明细 ≥2 卡显示 ★  
3. pytest + `npm run build` 绿  
