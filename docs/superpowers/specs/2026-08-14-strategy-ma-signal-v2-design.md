# 策略双均线信号加深（确认 N=2 + 强度档）设计

日期：2026-08-14  
状态：已批准（方案 1：扩展 `strategy_signal_ma`；交叉当日 hold，次日确认；强度档写入 payload）  
范围：仅 zak2；不新建算法模块；不改回测引擎；N/阈值本刀写死

## 背景

`warm_watchlist_strategy_cache` 已写日 K 双均线启发式（深度 1：交叉当日即 buy/sell）。看盘可读但易噪：当日交叉未确认、强度只有裸数值。

## 目标

1. 交叉确认 **N=2**：交叉发生在昨段，今仍同向才标 buy/sell；交叉当日 → hold（待确认）。  
2. 强度档：按 `|ma_gap_pct|` 分 弱/中/强，写入 payload 并透出到看盘。  
3. 升级 warm 文案；看盘强度列优先显示档位。  
4. 更新 smoke 与路线图 **#46**。

## 非目标

- 可调 N / 可调分档阈值 UI  
- 第二类策略算法、回测第二策略  
- 量比参与改档、改 config_key 格式  
- 下单、桌面 ShortBreakout 全规则

## 决策摘要

| 项 | 选择 |
|----|------|
| 架构 | 扩展现有 `strategy_signal_ma` |
| 确认 | N=2 写死：交叉当日 hold，次日同向发信 |
| 分档 | `<0.3` 弱 · `[0.3,1.0)` 中 · `≥1.0` 强 |
| UI | 强度列「档 · 数值」；不新开宽列 |

---

## 1. 算法

改 `compute_ma_signal`：

### 1.1 确认语义

对最近三根有效均线点 `k,j,i`（再前、昨、今）：

1. 用 `cross_kind(j→i)` 得「当日交叉」候选；若为 buy/sell → **hold**，`reason` 含「待确认」。  
2. 用 `cross_kind(k→j)` 得「昨交叉」；若昨为 buy 且今 `fast>slow` → **buy（已确认）**；若昨为 sell 且今 `fast<slow` → **sell（已确认）**。  
3. 否则 hold（含观望）。

数据不足 `slow + 2` 有效收盘 → 返回 `None`。

### 1.2 强度档

`gap_abs = abs(ma_gap_pct)`：

| 条件 | `strength_tier` | `strength_tier_label` |
|------|-----------------|------------------------|
| `< 0.3` | `weak` | 弱 |
| `0.3 ≤ x < 1.0` | `mid` | 中 |
| `≥ 1.0` | `strong` | 强 |

`strength` 仍为 `gap_abs`（排序不变）。量比不改档。

### 1.3 Payload 增字段

- `confirm_bars`: `2`  
- `strength_tier` / `strength_tier_label`  
- `reason_summary`：含「待确认」或「已确认」+ 档位标签（如「5/10 日均线金叉已确认（启发式·中）」）

---

## 2. Job 与 Schema

- `warm_watchlist_strategy_cache`：仍调 `compute_ma_signal`；`message` 与 catalog 描述含「确认 N=2」或「双均线启发式 v2」。  
- `StrategySignalRow` + 前端类型：可选 `strength_tier`、`strength_tier_label`。  
- `strategy_board` 从 payload 透出；缺字段时前端退回仅数值。

---

## 3. 看盘 UI

- 信号表「强度」列：有档 → `中 · 0.8`（档 + 数值）；无档 → 现状。  
- 摘要列展示含确认语义的 `reason_summary`。  
- 不新增独立「档」列；不改名单/持仓区。

---

## 4. 测试与文档

### 后端

- 交叉当日 → hold + 待确认  
- 昨交叉 + 今同向 → buy/sell + 已确认  
- 分档边界：0.29 / 0.3 / 1.0  
- warm message 含 v2/确认；board 透出 tier  

### 工程

- smoke：warm 后看盘可见档位/确认语义  
- roadmap **#46**；`./scripts/check.sh` 绿  

### 验收

1. 交叉当日不标 buy/sell。  
2. 确认次日同向 → buy/sell + 档。  
3. 看盘强度列可见档；check.sh 通过。

---

## 后续刀（非本范围）

可调 N/阈值；第二策略；回测第二策略；量比加权分档。
