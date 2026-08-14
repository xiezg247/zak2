# 看盘「入队回测」设计

日期：2026-08-14  
状态：已批准
范围：仅 zak2；复用现有回测入队 API；不下单  
前置：看盘 ↔ 回测对齐（#53）；trend_ma 看盘（#54）

## 背景

看盘已有「同参回测」：跳转 `/backtest` **仅预填**、不入队。用户仍需在回测页再点「开始回测」。产品希望在确认后可直接入队，同时保留误触安全的预填路径。

## 目标

1. 策略看盘增加 **「入队回测」**：confirm → `POST /api/v1/backtest/runs` → 跳转 `/backtest?job_id=` 并轮询。  
2. **「同参回测」** 行为不变（只预填）。  
3. 参数映射：模式 → 策略/窗口；区间/资金对齐回测页默认。  
4. 路线图 #55 + smoke；`./scripts/check.sh` 绿。

## 非目标

- 改「同参回测」为自动开跑  
- 新建专用入队 API / 批量 / 优化入队  
- 看盘内嵌进度 UI（除按钮 disabled + 短文案）  
- 服务端 `signal_mode` 偏好  
- 修改 CTA 引擎、交易下单  
- 分钟线入队（本刀固定 `interval=d`）

## 决策摘要

| 项 | 选择 |
|----|------|
| UX | 双按钮：同参预填 + 入队（confirm） |
| 入队 | 前端调现有 `backtestApi.start` |
| 跳转 | `/backtest?job_id=`，复用 `pollJob` |
| 默认区间/资金 | `2020-01-01`～`2026-06-01`，`100000`（对齐 BacktestView 表单） |
| heuristic | 映射为 `double_ma` + 解析窗口 |

---

## 1. UX

| 控件 | 行为 |
|------|------|
| 同参回测 | 跳转预填，不入队（不变） |
| 入队回测 | `confirm` 摘要 → `start` → `router.push({ path:'/backtest', query:{ job_id }})`；失败留看盘报错 |
| 进行中 | 入队按钮 disabled +「入队中…」 |

确认文案示例：`对 600519.SSE 入队 double_ma 5/20，区间 2020-01-01～2026-06-01，资金 100000？`

`vt_symbol` 选取顺序与同参一致：选中自选 → 信号首行 → 自选首行；皆无则不弹 confirm。

---

## 2. 参数映射

| 字段 | 规则 |
|------|------|
| `vt_symbol` | 见上 |
| `strategy` / 窗口 / ADX | `signalMode==='trend_ma'` → `trend_ma`、20/60、`adx_period=14`、`adx_threshold=25`、`trailing_stop_pct=0.12`；否则 → `double_ma` + 从 `board.config_key` 解析 fast/slow（失败 5/20） |
| `interval` | `d` |
| `start_date` / `end_date` | `2020-01-01` / `2026-06-01` |
| `capital` | `100000` |
| 费用 | 不传，用 API schema 默认 |

抽取与「同参回测」共用的「当前模式 → 回测参数」辅助函数，避免两处漂移。

---

## 3. BacktestView

`onMounted`：

1. 保留现有 query 预填（strategy / vt / windows / ADX）。  
2. 若 `job_id` 非空：`running=true` → 现有 `pollJob(job_id)` → 结束 `running=false`；**不得**因 `job_id` 再调 `start`。  
3. 刷新同 `job_id`：允许再轮询（终态 job 应立即结束）。

不改 jobs / ARQ / backtest worker 协议。

---

## 4. 模块边界

| 路径 | 变更 |
|------|------|
| `frontend/src/views/WatchlistView.vue` | 「入队回测」+ confirm + start + 跳转；参数 helper |
| `frontend/src/views/BacktestView.vue` | `job_id` query → `pollJob` |
| `frontend/src/api/backtest.ts` | 一般无需改（已有 `start`） |
| docs | #55、smoke、本 spec |

后端：本刀无强制 schema/API 变更（除非测试需补前端契约说明）。

---

## 5. 验收

- [ ] 「同参回测」仍只预填、不入队  
- [ ] 「入队回测」confirm 后入队并跳转；页内轮询出结果或失败文案  
- [ ] heuristic / double_ma → double_ma；trend_ma → trend_ma + ADX  
- [ ] 无标的时不入队并提示  
- [ ] `./scripts/check.sh` 绿  
- [ ] 路线图 #55 + smoke  

## 风险

| 风险 | 缓解 |
|------|------|
| 误触入队 | confirm；同参路径保留 |
| 重复刷新轮询 | poll 对终态快速返回 |
| 区间与 schema 默认 end 不一致 | 显式传 BacktestView 表单值，不依赖 schema end 默认 |

## 后续刀

- 服务端模式偏好  
- 入队前可改区间/资金小表单  
- 分钟线 / 批量入队
