# 日K / 1分 K 线切换设计

日期：2026-08-13  
状态：已批准（方案 1：自选+市场就地周期切换；limit 芯片随周期；CandleChart 轴标签）  
范围：仅 zak2；读已有 `GET /bars`；不下载、不推送、不持久化偏好

## 背景

关注池 1m 已可由 Ops `fill_focus_pool_minute` 写入 `dbbardata`；`load_bars` 支持 `interval=1m`。自选 / 市场详情图仍写死 `'d'`，有数据无图。`load_bars` 404 文案写死「补全日 K」，对 1m 误导。

## 目标

1. 自选与市场详情可在 **日K / 1分** 间切换并出图。  
2. limit 芯片随周期切换（日：60/90/120；1分：240/480/1200）。  
3. 无 1m 时空态链 Ops（对应 `fill_focus_pool_minute`）。  
4. `CandleChart` 按周期显示合适时间轴；更新 smoke 与路线图。

## 非目标

- 自动下载分钟线 / 其它周期（5m…）UI  
- 实时推送、localStorage 记住周期  
- 抽大面板组件、新建 bars API  
- 市场页新增 OHLC 小表

## 决策摘要

| 项 | 选择 |
|----|------|
| 入口 | 自选 + 市场详情 |
| 周期 | 仅 `d` \| `1m` |
| 空态 | 链 `/ops`；1 分提示补全 1 分 K |
| limit | 日 60/90/120（默认 90）；1 分 240/480/1200（默认 480） |
| 架构 | 双页就地扩展 + CandleChart prop |

---

## 1. 读路径与 404 文案

继续 `GET /api/v1/bars/{vt_symbol}?interval=&limit=`。

- UI 只传 `d` | `1m`。  
- limit：后端仍 `max(1, min(limit, 2000))`。  
- `load_bars` 无行时 404 `detail`：  
  - `d` →「无 K 线数据，请先在 Ops 补全日 K」  
  - `1m` →「无 1 分 K 线，请先在 Ops 运行 fill_focus_pool_minute」  
  - 其它 →「无 K 线数据」

不新增端点、不在读路径触发下载。

---

## 2. 前端 UI（WatchlistView / MarketView）

两页行为一致：

| 控件 | 行为 |
|------|------|
| 周期芯片 | `日K` \| `1分`；切换后按当前标的重拉 |
| limit 芯片 | 日：`60日`/`90日`/`120日`；1分：`240`/`480`/`1200`（可标「根」） |
| 默认 | 日 90；1 分 480 |
| 加载文案 | 「加载日 K…」/「加载 1 分 K…」 |
| 空态/错误 Ops 链 | 日 →「补全日 K」；1 分 →「补全 1 分 K」 |
| meta（自选） | 区间 + 根数；单位随周期 |
| 切标的 | **保留**当前周期与对应 limit |

自选保留 OHLC 小表：1 分时日期列展示含时分的 `datetime`。市场仅图 + 控件，不加表。

---

## 3. CandleChart

- 新增可选 prop：`interval?: 'd' | '1m'`（默认 `'d'`）。  
- x 轴：日 → `MM-DD`；1 分 → `HH:MM`。  
- 底部 hint：日 → `YYYY-MM-DD`；1 分 → `MM-DD HH:MM`。  
- 不改蜡烛/成交量几何。

---

## 4. 测试与文档

### 后端

- 无数据：`interval=1m` 的 404 detail 含「1 分」与 `fill_focus_pool_minute`；`d` 文案不变。

### 工程

- smoke：自选/市场可切 1 分；无数据有 Ops 链；有数据出图。  
- roadmap **#45**；`./scripts/check.sh` 绿。

### 验收

1. 两页日K ↔ 1分可切换，limit 芯片随周期变。  
2. 有 1m：出图，轴为时分。  
3. 无 1m：空态链 Ops。  
4. check.sh 通过。

---

## 后续刀（非本范围）

5m/15m UI；偏好持久化；公共 BarChartPanel；读路径触发补数。
