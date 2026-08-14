# 看盘 ↔ 回测信号对齐（双模式）设计

日期：2026-08-14  
状态：待用户审阅  
范围：仅 zak2；不改 CTA 引擎买卖语义；不做 trend_ma 看盘  
前置：策略看盘启发式 v2（#46）；回测 `double_ma`（#49）

## 背景

策略看盘经 `warm_watchlist_strategy_cache` 写 `watchlist_signal_cache`，算法为日 K 双均线**确认 N=2**启发式（`compute_ma_signal`）。回测 `double_ma` 为 vnpy CTA，**交叉当日**买卖。同日金叉时两边信号可不一致；多份回测 spec 将「共用信号」列为后续。

产品选择：**双模式**——warm 预热两套 cache；看盘可切换；一键同参跳转回测。不把确认逻辑硬塞进 CTA，也不强行取消看盘确认。

## 目标

1. warm 同时写入 `heuristic_v2`（兼容现 key）与 `double_ma:{fast}:{slow}`。  
2. `GET strategy-board` 支持 `signal_mode=heuristic_v2|double_ma`（默认 heuristic）。  
3. 看盘 UI 可切换模式；文案标明差异。  
4. 「同参回测」链到 `/backtest` 预填参数，不自动入队。  
5. 抽取共享 `sma` / `cross_kind`；路线图 #53 + smoke。

## 非目标

- `trend_ma` 看盘模式  
- 修改 `DoubleMaStrategy` / `TrendMaStrategy` 确认棒或 ADX  
- 请求路径现算信号（仍只读 cache）  
- 伪造桌面 Redis `double_ma` 桥键  
- LLM、下单

## 决策摘要

| 项 | 选择 |
|----|------|
| 落法 | config_key 后缀双轨 cache（非同 key 嵌 modes） |
| 默认展示 | `heuristic_v2` |
| 预热 | warm 两种都算（切换即时） |
| 回测联动 | 预填跳转，不自动跑 |
| CTA | 不改 |

---

## 1. 架构与 key 规范

```
warm_watchlist_strategy_cache
  ├─ 既有 keys（如 AshareShortBreakoutStrategy:5:10）
  │     → compute_ma_signal → cache（signal_mode=heuristic_v2）
  └─ 派生 double_ma:{fast}:{slow}
        → compute_double_ma_signal → cache（signal_mode=double_ma）
              ↓
GET /watchlist/strategy-board?signal_mode=
  resolve_config_key_for_mode → 读 Redis/PG
              ↓
WatchlistView：模式切换 + 同参回测 → /backtest?…
```

| 模式 | config_key | 说明 |
|------|------------|------|
| `heuristic_v2` | 现状不变（`DEFAULT_CONFIG_KEY` / 用户偏好类名 key） | 兼容桌面桥 |
| `double_ma` | `double_ma:{fast}:{slow}` | 与回测 strategy id 对齐 |

- `double_ma` 的 fast/slow：来自用户当前 `signal_config` 解析出的窗口；若无则 **5:20**（对齐 BacktestView 默认）。  
- warm：对每个可 `parse_config_key` 的 heuristic key 派生同窗口 `double_ma:…`；并保证至少 `double_ma:5:20`。

共享模块（建议 `app/services/ma_cross.py` 或留在 `strategy_signal_ma` 再导出）：`sma`、`cross_kind`；确认逻辑仅 heuristic 使用。

---

## 2. `double_ma` 信号规则

`compute_double_ma_signal(closes, *, volumes=None, fast, slow, vt_symbol, as_of) -> dict | None`

| 条件 | signal |
|------|--------|
| 金叉（昨 fast≤slow 且今 fast>slow） | `buy` |
| 死叉（对称） | `sell` |
| 否则 | `hold` |

- 无确认棒、无 `pending`  
- 仍写 `ma_gap_pct`、`strength_tier` / `strength_tier_label`  
- `reason_summary` 含「双均线当日交叉（对齐回测 double_ma）」  
- payload 含 `signal_mode: "double_ma"`；heuristic 写入 `signal_mode: "heuristic_v2"`  
- 最低根数：`slow + 1`（需昨今两根有效均线即可）

---

## 3. warm 变更

文件：`ops_warm_watchlist_strategy.py`

1. `_list_config_keys` 逻辑保留（含 DEFAULT + 用户偏好）。  
2. `_compute_pool`：对每个 key  
   - 若像现状可算 → `compute_ma_signal` upsert  
   - 若 `parse_config_key` 成功 → 另 upsert `double_ma:{fast}:{slow}` via `compute_double_ma_signal`  
3. 循环结束后若尚无 `double_ma:5:20` 计算，补跑该 key。  
4. `_bridge_config`：仍只扫桌面/既有 Redis 前缀；**不对** `double_ma:*` 做假桥。  
5. job `message` / catalog：标明双轨预热。

---

## 4. API 与 resolve

### `resolve_board_config_key(db, user_id, *, signal_mode, override=None) -> str`

- `heuristic_v2`：等同现 `resolve_config_key`  
- `double_ma`：取用户偏好的 (fast,slow) 或默认 5,20 → `double_ma:{fast}:{slow}`  
- `override` 若已是完整 key 且合法，可直接用（高级/调试）

### `GET /api/v1/watchlist/strategy-board`

| Query | 默认 | 说明 |
|-------|------|------|
| `signal_mode` | `heuristic_v2` | `heuristic_v2` \| `double_ma` |
| 既有 `config_key` | 可选 | 兼容覆盖 |

响应 `StrategyBoardOut` 增：

- `signal_mode: str`  
- `note`：两模式差异短文（切 mode 时更新）

打包行时透出 payload 中的 `signal_mode`（若有）。

---

## 5. UI（Watchlist 策略看盘）

| 控件 | 行为 |
|------|------|
| 模式切换 | `启发式确认` / `回测双均线`；切换后带 `signal_mode` 重拉 board |
| 副文案 | heuristic：确认 N=2；double_ma：当日交叉，对齐 `/backtest` |
| 同参回测 | 对当前关注标的（信号表选中行或首行/自选当前票，实现取**信号行点击或表头按钮+当前 vt**）：`router.push({ path:'/backtest', query:{ strategy:'double_ma', fast, slow, vt_symbol }})` |
| BacktestView | 读 query 预填 strategy/fast/slow/vt；**不**自动 `startRun` |

强度列两模式共用现有展示。

---

## 6. 模块边界

| 路径 | 变更 |
|------|------|
| `strategy_signal_ma.py`（+ 可选 `ma_cross.py`） | 共享交叉；`compute_double_ma_signal` |
| `ops_warm_watchlist_strategy.py` | 双轨 upsert |
| `strategy_board.py` | mode → key；Out 字段；note |
| `api/v1/watchlist.py` | query `signal_mode` |
| `schemas/watchlist.py` | `signal_mode` |
| `ops_catalog.py` | warm 描述 |
| `WatchlistView.vue` / `watchlist.ts` | 切换 + 回测链 |
| `BacktestView.vue` | query 预填 |
| 测试 | double_ma 当日交叉；warm 写两 key；board mode 解析；Backtest query |

---

## 7. 验收

- [ ] warm 后同票 heuristic key 与 `double_ma:…` 均有 cache  
- [ ] 切 `double_ma` 后交叉日信号可与 heuristic（待确认/hold）不同  
- [ ] 同参回测打开 `/backtest` 且参数预填，未自动开跑  
- [ ] heuristic 默认路径回归  
- [ ] `./scripts/check.sh` 绿  
- [ ] 路线图 #53 + smoke  

## 风险

| 风险 | 缓解 |
|------|------|
| warm 耗时 ×2 | 池 cap 500 已有；仅多一轮同 closes 计算 |
| key 膨胀 | 仅派生可解析窗口 + 默认 5:20 |
| 用户误以为完全同一引擎 | UI/note 标明「对齐规则，非 vnpy 进程」 |

## 后续刀

- `trend_ma` 看盘快照  
- 用户权重/模式持久偏好  
- 看盘触发回测入队（需确认）
