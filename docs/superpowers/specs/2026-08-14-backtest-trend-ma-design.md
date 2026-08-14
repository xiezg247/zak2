# 回测第二策略 trend_ma 设计

日期：2026-08-14  
状态：待用户审阅  
范围：仅 zak2；不改 zak；**禁止** import `vnpy_ashare` / zak 策略包  
前置：vnpy CTA 回测主路径已落地（`docs/superpowers/specs/2026-08-14-vnpy-backtest-deepen-design.md`）

## 背景

回测目前仅注册 `double_ma`。桌面另有日 K 趋势策略 `AshareTrendMaStrategy`（双均线 + ADX 过滤 + 追踪止损）。本刀在 zak2 内按同一语义增加第二条可跑策略，打通最小闭环。

## 目标

1. 新增策略 id `trend_ma`，CTA 类可被 `BacktestingEngine` 加载。  
2. 单票 / 批量回测可选 `trend_ma` 并落库。  
3. UI 策略下拉出现「趋势双均线（ADX）」。  
4. 语义对齐桌面 `AshareTrendMaStrategy`（只读参考，不 import）。

## 非目标

- 新策略画像 chip  
- 优化网格扩展 ADX / 止损参数（仍只扫 `fast_window`/`slow_window`；其余用默认或请求值）  
- 分钟线、组合回测  
- 与策略看盘共用信号实现  
- 改 zak / 引入桌面策略类

## 决策摘要

| 项 | 选择 |
|----|------|
| 策略 | `trend_ma` ← 桌面 TrendMa 语义重写 |
| 落法 | 独立 CTA 文件 + registry（不堆进 DoubleMa） |
| 范围 | 最小闭环：类 + 注册 + API 放行 + UI 下拉 |
| ADX | `ArrayManager.adx`（vnpy trader utility）；不可用则自实现同周期 ADX |
| 画像 | 不新增；既有画像仍只填 fast/slow/capital |

## 策略语义

默认参数（与桌面对齐）：

| 参数 | 默认 |
|------|------|
| `fast_window` | 20 |
| `slow_window` | 60 |
| `adx_period` | 14 |
| `adx_threshold` | 25.0 |
| `trailing_stop_pct` | 0.12 |
| `trade_volume` | 100 |

**买入（空仓时）** 同时满足：

- 金叉：`fast_ma0 > slow_ma0` 且 `fast_ma1 <= slow_ma1`
- `adx_value >= adx_threshold`
- `close > slow_ma0` 且 `slow_ma0 >= slow_ma1`（慢线向上）

**卖出（持仓时）** 任一满足：

- 死叉
- 结构破位：`close < slow_ma0`
- 追踪止损：`close < highest_since_entry * (1 - trailing_stop_pct)`

持仓期间用收盘价更新 `highest_since_entry`。买卖走 `AShareCtaTemplate`（整手 100、T+1）。

预热：`ArrayManager` size ≥ `max(slow_window, adx_period * 2) + 10`；`on_bar` 在 `am.count < max(slow_window, adx_period * 2) + 2` 时直接返回。

## 模块与接口

| 路径 | 变更 |
|------|------|
| `app/strategies/cta/trend_ma.py` | 新建 `TrendMaStrategy` |
| `app/strategies/cta/registry.py` | 注册 `trend_ma` |
| `app/services/backtest_engine.py` | `STRATEGIES` 增加一条 |
| `app/schemas/backtest.py` | 可选字段：`adx_period` / `adx_threshold` / `trailing_stop_pct`（有默认）；`BatchBacktestRequest` 同步 |
| `app/services/backtest_repo.py` | 允许 `trend_ma`；`setting` 按策略组装（含 ADX/止损） |
| `app/worker/tasks_backtest.py` | subprocess setting 同步透传 |
| `frontend/.../BacktestView.vue` | 依赖 `/strategies` 列表即可；无需写死 id（确认下拉绑 `strategies`） |

`execute_single` 今日硬编码 `strategy != "double_ma" → 501`，改为：`get_strategy_class(strategy)` 失败 → 501。

## 优化行为（本轮）

选 `trend_ma` 跑 `/optimize` 时：网格仍只变 `fast`/`slow`；`adx_*` / `trailing_stop_pct` 用请求体默认值。不在 UI 优化 Tab 增加新输入框。

## 测试

1. `get_strategy_class("trend_ma")`  
2. `@pytest.mark.vnpy` 合成日 K：`run_cta_backtest(..., strategy_id="trend_ma")` 返回含 `statistics` / 不抛错  
3. API 层或 repo：未知策略仍 501  

## 验收

- [ ] UI 可选 `trend_ma` 并成功入队跑通（需日 K + backtest-worker）  
- [ ] 结果 `strategy=trend_ma`，`params` 含 ADX/止损快照  
- [ ] `double_ma` 回归不受影响  
- [ ] `./scripts/check.sh` 绿  
- [ ] 路线图增加完成项并链本 spec  

## 风险

| 风险 | 缓解 |
|------|------|
| `ArrayManager.adx` 行为与桌面略异 | 对照桌面公式；单测合成序列 |
| 慢线 60 需要更长日 K | `trend_ma` 最低日 K 根数 = `max(30, slow_window + adx_period * 2 + 5)`（默认约 93）；不足则 `failed`，文案含实际根数与要求 |
