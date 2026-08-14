# 回测分钟线（1m）设计

日期：2026-08-14  
状态：待用户审阅  
范围：仅 zak2；不改 zak；不 import `vnpy_ashare`  
前置：vnpy CTA 回测 + `double_ma` / `trend_ma`；关注池 1m 已可写入 `dbbardata`

## 背景

回测主路径已切 vnpy，但行情注入与引擎参数写死日 K（`Interval.DAILY` / `interval=d`）。PG 已有 `interval=1m`（Ops `fill_focus_pool_minute`）。本刀打通 **1m 回测最小闭环**：可选周期、加载分钟 K、现有策略在 1m bar 上可跑，并控制单次数据量。

## 目标

1. 请求支持 `interval=1m`（默认仍 `d`）。  
2. 从 `public.dbbardata` 加载 1m → 注入 `history_data`，引擎使用 `Interval.MINUTE`。  
3. `double_ma` / `trend_ma` 在 1m 上可跑（均线窗口按 **bar 根数**，非交易日）。  
4. 1m 单次默认最多 **20** 个交易日，可配置，硬顶 **60**。  
5. 1m 不足时 failed，文案引导 Ops `fill_focus_pool_minute`。  
6. UI 可选周期，并提示 1m 上限与补数入口。

## 非目标

- 新分钟专用策略（突破/打板等）  
- 5m / 15m / 30m / 60m  
- 全市场自动补 1m  
- 与策略看盘共用信号  
- 改 zak

## 决策摘要

| 项 | 选择 |
|----|------|
| 落法 | 扩展现有管线（通用 load + Interval 映射），不另起 minute 模块 |
| 策略 | 复用现有两条 CTA；参数含义变为「分钟根」 |
| 数据范围 | 库中有 1m 即可；不强制关注池（下载仍靠现 Ops） |
| 体量 | `max_trading_days` 默认 20，硬顶 60 |
| 交易日判定 | 用区间内 **有 1m bar 的 distinct 日历日** 计数；超过则 API 400 或执行前 failed |

## 行为细则

### 请求字段

- `interval`: `"d"` | `"1m"`，默认 `"d"`  
- `max_trading_days`: int，仅 `1m` 生效；默认 20；`1 ≤ n ≤ 60`  
- 单票 / 批量 / 优化请求均支持（优化 1m 时同样受天数上限）

### 加载

- 将 `load_daily_bars` 泛化为 `load_bars(..., interval, min_bars=...)`（或并列 `load_minute_bars` 共用核心）。  
- `interval=1m`：`DbBarData.interval == "1m"`；时间戳保留到分钟。  
- 最低根数：  
  - `d`：沿用现逻辑（`double_ma` 30；`trend_ma` 按 slow/adx 公式）  
  - `1m`：至少 `max(min_bars_strategy, 100)`（保证均线预热；可按策略再调）  
- 交易日跨度：对结果集按 `datetime.date` distinct 计数；若 `> max_trading_days` → 400，detail 含实际天数与上限（提示缩小区间）。

### 引擎

- `records_to_bars` / `set_parameters`：`d` → `Interval.DAILY`；`1m` → `Interval.MINUTE`（vnpy 常量以安装版为准，映射集中一处）。  
- `run_cta_backtest(..., interval=)` 透传。  
- 落库 `BacktestRun.interval` 写实际 `"1m"` / `"d"`；`params_json` 含 `max_trading_days`（1m 时）。

### 费用 / 夏普

- 费用参数不变。  
- vnpy 统计对分钟样本的年化假设可能与日 K 不同；UI 在 1m 结果旁短注「分钟样本，指标口径与日 K 不完全可比」即可，本刀不重算年化公式。

### UI（`/backtest`）

- 周期选择：`日 K` / `1 分钟`。  
- 选 1m：显示「默认最多 20 个交易日」；可改数字（≤60）；错误/失败时链 Ops（文案点名关注池 1m 补全）。  
- 策略下拉不变；选 1m 时副文案：均线窗口按分钟 K 根数。

## 模块边界

| 路径 | 变更 |
|------|------|
| `app/schemas/backtest.py` | `interval` 校验；`max_trading_days` |
| `app/services/backtest_bars.py` | 通用加载 + 交易日计数校验 |
| `app/services/backtest_vnpy.py` | Interval 映射 |
| `app/services/backtest_repo.py` / worker | 透传 interval / max_trading_days |
| `app/services/backtest_engine.py` | STRATEGIES 描述可注明支持 d/1m |
| `frontend/.../BacktestView.vue` | 周期与上限控件 |
| 测试 | 1m 合成 records 冒烟；超天数 400；缺 K 文案 |

## 验收

- [ ] `interval=1m` 有足够分钟 K 时可跑通 `double_ma`（及 `trend_ma`）  
- [ ] 交易日超过上限被拒绝，文案可读  
- [ ] 无 1m 时 failed 并导向 Ops 补分钟 K  
- [ ] `interval=d` 回归不受影响  
- [ ] `./scripts/check.sh` 绿  
- [ ] 路线图 + smoke 更新  

## 风险

| 风险 | 缓解 |
|------|------|
| 1m 数据量大 | 默认 20 日硬顶 60 |
| 均线参数在分钟上过「快」 | UI 提示；画像仍偏日 K，用户自调 |
| Tushare 分钟权限 | 补数失败保持 Ops 现有错误，不伪装 |
| vnpy `Interval.MINUTE` 命名 | 实现时对安装版做常量探测/单测钉死 |
