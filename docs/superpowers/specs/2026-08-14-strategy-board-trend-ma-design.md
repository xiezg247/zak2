# 看盘 trend_ma + 模式偏好持久化设计

日期：2026-08-14  
状态：草稿（待审阅）  
范围：仅 zak2；不改 CTA 引擎买卖语义；不做看盘入队回测  
前置：看盘 ↔ 回测信号对齐（#53）；回测 `trend_ma`（#50）

## 背景

#53 已提供 `heuristic_v2` / `double_ma` 双模式与同参回测预填。回测另有 `trend_ma`（双均线 + ADX + 追踪止损），看盘尚无对应快照。模式切换目前会话内有效，刷新后回到默认启发式。

产品选择：warm 增加 **第三轨** `trend_ma:20:60`；UI 第三模式；**localStorage** 记住 `signal_mode`。卖点在无仓时简化（不算追踪止损）。

## 目标

1. `compute_trend_ma_signal`：入场对齐 CTA；无仓卖点 = 死叉或跌破慢线。  
2. warm 写入 `trend_ma:20:60`（固定窗口）；日 K 加载含 H/L/C。  
3. `signal_mode=trend_ma` 解析固定 key；board `note` 标明差异。  
4. Watchlist 三模式 + localStorage 持久；同参回测在 trend 模式预填 `trend_ma` + ADX 默认。  
5. 路线图 #54 + smoke；`./scripts/check.sh` 绿。

## 非目标

- 修改 `TrendMaStrategy` / `DoubleMaStrategy`  
- 看盘模拟仓位 / 追踪止损参与判定  
- 请求路径现算信号  
- 服务端持久 `signal_mode`  
- 看盘触发回测入队  
- UI 调 20:60 / ADX  
- 伪造 Redis `trend_ma:*` 桥  
- LLM、下单

## 决策摘要

| 项 | 选择 |
|----|------|
| 落法 | #53 三轨 cache 扩展 |
| 窗口 | 固定 CTA 默认 **20:60** |
| ADX / trail | 看盘判定用 14 / 25；trail **0.12 仅同参预填** |
| 卖点 | 死叉或 close&lt;慢线；**不算**追踪止损 |
| 偏好 | `localStorage` `zak2:watchlist:signal_mode` |
| CTA | 不改 |

---

## 1. 架构与 key

```
warm_watchlist_strategy_cache
  ├─ heuristic keys → compute_ma_signal
  ├─ double_ma:{fast}:{slow} → compute_double_ma_signal
  └─ trend_ma:20:60 → compute_trend_ma_signal
        ↓
GET /watchlist/strategy-board?signal_mode=heuristic_v2|double_ma|trend_ma
        ↓
WatchlistView：三模式 + localStorage
「同参回测」→ /backtest 预填（不自动开跑）
```

| 模式 | config_key |
|------|------------|
| `heuristic_v2` | 现状 |
| `double_ma` | `double_ma:{fast}:{slow}` |
| `trend_ma` | **`trend_ma:20:60`**（ADX/trail 不进 key） |

仍只读 cache；Redis 桥不伪造 `trend_ma:*`。

---

## 2. `trend_ma` 信号规则

`compute_trend_ma_signal(highs, lows, closes, *, volumes=None, fast=20, slow=60, adx_period=14, adx_threshold=25.0, vt_symbol, as_of) -> dict | None`

| 条件 | signal |
|------|--------|
| 金叉且 ADX≥阈值且 close&gt;慢线且慢线上行 | `buy` |
| 死叉或 close&lt;慢线 | `sell` |
| 否则 | `hold` |

- 无确认棒、无持仓回放、不算追踪止损  
- payload：`signal_mode: "trend_ma"`；建议含 `adx_value`、`ma_gap_pct`、强度档（`strength_tier_for`）  
- `reason_summary` 标明「趋势均线看盘（对齐入场；卖点不含追踪止损）」  
- 最低根数：`max(slow, adx_period * 2) + 2`  
- ADX：纯 Python Wilder（不 import vnpy）

常量：`TREND_MA_FAST=20`、`TREND_MA_SLOW=60`、`ADX_PERIOD=14`、`ADX_THRESHOLD=25.0`、`TRAILING_STOP_PCT=0.12`（后者仅预填）。

---

## 3. warm

文件：`ops_warm_watchlist_strategy.py`

1. `_load_daily_*` 返回 highs/lows/closes/volumes/as_of（closes 供既有两轨）。  
2. 池内每标的在 heuristic / double_ma 之后，用同批 OHLC upsert `trend_ma:20:60`。  
3. 池非空则保证写过该 key。  
4. `_bridge_config` 不扫 `trend_ma:*`。  
5. catalog / job `message`：三轨字样。

---

## 4. API 与 resolve

- `SIGNAL_MODE_TREND_MA = "trend_ma"`  
- `trend_ma_config_key() -> "trend_ma:20:60"`  
- `resolve_board_config_key`：mode=`trend_ma` → 固定 key；`override` 非空仍优先  
- 非法 `signal_mode` → 回退 `heuristic_v2`  
- `note`：趋势模式说明入场对齐、卖点无追踪止损、非 vnpy 进程  

Query `signal_mode` 合法值：`heuristic_v2` \| `double_ma` \| `trend_ma`。

---

## 5. UI / 偏好

| 控件 | 行为 |
|------|------|
| 三模式钮 | 启发式确认 / 回测双均线 / 趋势均线 |
| localStorage | key=`zak2:watchlist:signal_mode`；切换即写；挂载时读；非法→heuristic |
| 同参回测 | `trend_ma`：`strategy=trend_ma`，fast/slow=20/60，带 adx_period/adx_threshold/trailing_stop_pct；其余模式仍 double_ma + 从 config_key 解析窗口 |
| BacktestView | 增读 ADX/trail query 预填；不自动 `startRun` |

---

## 6. 模块边界

| 路径 | 变更 |
|------|------|
| `strategy_signal_ma.py` | `compute_trend_ma_signal` + ADX 辅助 |
| `ops_warm_watchlist_strategy.py` | OHLC 加载 + 第三轨 |
| `strategy_board.py` | mode / key / note |
| `ops_catalog.py` | 文案 |
| `WatchlistView.vue` / `watchlist.ts` | 三模式 + localStorage + 预填 |
| `BacktestView.vue` | ADX query |
| docs | #54、smoke、本 spec |
| 测试 | 信号 / warm upsert / resolve |

---

## 7. 验收

- [ ] warm 后存在 `trend_ma:20:60` cache  
- [ ] 切趋势模式可读信号；note 含卖点简化说明  
- [ ] 刷新页面仍保持上次 mode  
- [ ] 同参回测预填 `trend_ma` + 默认 ADX，未自动开跑  
- [ ] heuristic / double_ma 回归  
- [ ] `./scripts/check.sh` 绿  
- [ ] 路线图 #54 + smoke  

## 风险

| 风险 | 缓解 |
|------|------|
| warm 多一轮 + OHLC | 池 cap 500；同一次查询复用 |
| 用户以为含追踪止损 | note / reason 明示 |
| ADX 与 vnpy 数值微差 | 文档写「规则对齐，非逐 tick 一致」 |

## 后续刀

- 看盘入队回测（需确认）  
- 服务端模式偏好  
- 可调 trend 参数 / 含追踪止损的仓位回放
