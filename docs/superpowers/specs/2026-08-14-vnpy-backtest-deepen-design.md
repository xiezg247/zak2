# 回测加深（Worker 内嵌 vnpy CTA）设计

日期：2026-08-14  
状态：已批准（实现中 / feat/vnpy-backtest-deepen）  
范围：zak2 回测路径；**backtest-worker 允许 import `vnpy` / `vnpy_ctastrategy`（PyPI）**；不改 zak 仓库；**禁止** import `vnpy_ashare` / 其它 zak 包

## 背景

zak2 回测当前为 P5 薄实现：自研日 K 双均线（`backtest_engine.run_double_ma`），经 ARQ 异步落 `app.backtest_runs`，UI 在 `/backtest`。

已知缺口：

- 撮合简化（同日收盘成交，存在前瞻偏差风险）
- 费用仅比例佣金；无滑点/印花税/涨跌停建模
- 指标仅收益、最大回撤、简化夏普、成交次数
- 策略仅 `double_ma`，与桌面 CTA / 策略看盘未统一运行时
- 无参数扫描；批量失败容错弱

产品选择：**不做「仅加深自研」或 VectorBT**；采用 **Worker 内嵌官方 vnpy CTA `BacktestingEngine`**，本轮一次做完整（引擎切换 + 可信费用 + 厚报告 + 网格优化 + UI）。

与历史「zak2 不 import vnpy_*」约定的关系：本功能对 **backtest-worker** 开例外；API 镜像与其它模块仍禁止。

## 目标

1. 单票 / 批量回测主路径改为 vnpy CTA 引擎；结果落库并在 `/backtest` 展示完整统计。  
2. 行情继续来自 PG `public.dbbardata`，经 zak2 加载后注入 `engine.history_data`（不依赖 `~/.vntrader` / vnpy Database）。  
3. 双均线策略在 zak2 内按 CTA 模板重写，语义对齐桌面 `AshareDoubleMaStrategy`（整手、T+1），不改 zak、不 import zak 包。  
4. 支持费用参数（佣金 / 滑点 / 印花税）与参数网格优化（硬顶 64 组）。  
5. 独立 `backtest-worker` 镜像与队列；批量 / 优化用子进程隔离。  
6. 失败可诊断（落库 `status` / `error_message`）；缺 K 仍导向 Ops。

## 非目标

- 分钟线 / Tick 回测  
- 实盘 / 纸面交易桥接  
- GA / 遗传优化（仅网格）  
- 多策略组合 / 组合级回测  
- 改 zak / `vnpy-*` 仓库代码；import `vnpy_ashare`  
- API 进程内安装或运行 vnpy  
- 静默回退到旧薄引擎  
- 强制数值与旧薄引擎逐字段一致（引擎已换，旧结果仅作历史说明）

## 决策摘要

| 项 | 选择 |
|----|------|
| 引擎 | PyPI `vnpy` + `vnpy_ctastrategy.BacktestingEngine` |
| 依赖来源 | 仅 PyPI；策略在 zak2 重写 |
| 进程模型 | 独立 backtest-worker；单票可同进程；批量/优化 spawn 子进程 |
| 行情 | PG `dbbardata` → `BarData` → `history_data`（绕过 `load_data()`） |
| 首期策略 | `double_ma`（可扩展注册表） |
| 优化 | 网格，≤64 组；目标默认 `sharpe_ratio` |
| 薄引擎 | 生产路径下线；删除生产引用（测试对照非必须） |
| 其它框架 | 已评估 VectorBT / 自研 / RQAlpha；本轮坚持 vnpy |

## 架构与数据流

```
UI /backtest
  → POST /api/v1/backtest/runs | /runs/batch | /optimize
  → Redis ARQ queue: backtest
  → zak2-backtest-worker（独立镜像）
       ├─ single：同进程跑引擎
       └─ batch / optimize：每任务 spawn 子进程
  → 读 PG public.dbbardata
  → 转 vnpy BarData → engine.history_data
  → set_parameters → add_strategy → run_backtesting
       → calculate_result / calculate_statistics
  → 映射 → app.backtest_runs
  → 前端 poll job → GET 详情
```

| 组件 | 职责 | vnpy 依赖 |
|------|------|-----------|
| API | 鉴权、校验、入队、读历史 | 无 |
| Ops / 其它 worker | 既有任务 | 无 |
| backtest-worker | 回测与优化 | 有 |
| 子进程 runner | 单引擎生命周期 | 有 |

### 关键实现要点

1. **行情注入**：复用 / 演进现有日 K 加载；转换为 `vnpy.trader.object.BarData` 列表，赋值 `engine.history_data`，**不调用**依赖 vnpy 自有库的 `load_data()`。  
2. **策略位置**：`backend/app/strategies/cta/`；薄 `AShareCtaTemplate`（整手 100、T+1、买卖封装）+ `DoubleMaStrategy`。  
3. **默认合约 / 费用参数**（请求可覆盖）：  
   - `size=1`，`pricetick=0.01`  
   - `rate=0.00045`（佣金，双边按成交额；与现薄引擎默认对齐）  
   - `slippage=0.0`（首期默认 0；UI 可调）  
   - `stamp_duty=0.0005`（印花税，仅卖出；在模板卖出路径或费用汇总中体现，并写入 `params_json`）  
4. **间隔**：首期仅日 K（`Interval.DAILY` / `"d"`）。

## API

前缀：`/api/v1/backtest`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/strategies` `/profiles` | 保留；元数据含 `engine: vnpy` |
| GET | `/runs` `/runs/{id}` `/batches` | 保留；详情含完整 `statistics` |
| POST | `/runs` | 单票；可选 `rate` / `slippage` / `stamp_duty` |
| POST | `/runs/batch` | 批量；上限可至 50（子进程池限流） |
| POST | `/optimize` | 参数网格；返回 `JobAccepted` + `batch_id` |
| GET | `/optimize/{batch_id}` | 最优 + 全部试次摘要 |

校验（API 层，不入队）：

- `fast_window < slow_window`  
- 优化笛卡尔积 ≤ 64，且每组满足 `fast < slow`  
- 日期格式、`capital > 0`、符号列表非空

## 数据模型

`app.backtest_runs` 兼容演进（Alembic migration）：

| 列 | 说明 |
|----|------|
| 既有指标列 | `total_return` / `max_drawdown` / `sharpe_ratio` / `trade_count` 保留 |
| `raw_statistics_json` | 完整 vnpy stats + 权益/成交（细节与现 JSON 约定对齐） |
| `engine` | `vnpy`；历史行可空或回填说明为旧薄引擎 |
| `params_json` | 策略参数 + 费用快照（可复现） |
| `status` | `success` / `failed` |
| `error_message` | 失败原因 |

优化：`source=optimize`，同一 `batch_id` 多行 = 各参数试次；`statistics` / `params_json` 含 `setting`。汇总由 `GET /optimize/{batch_id}` 聚合（默认按 `sharpe_ratio` 排序）。

## 参数扫描

- 请求：`vt_symbol`、日期、`capital`、费用、`space`（如 `fast_window` / `slow_window` 数组）、可选 `objective`（默认 `sharpe_ratio`）。  
- Worker：过滤非法组合 → 子进程池执行 → 逐条 `save_run`。  
- 首期仅网格；不做 GA。

## UI（`/backtest`）

1. 费用区（可折叠，有默认）。  
2. 结果卡加厚：年化、波动、胜率、盈亏比、最大回撤区间等（取自 `statistics`）。  
3. 成交表可展开（取消硬截断 40，或「显示全部」）。  
4. 优化 Tab：参数范围 → 试次表 → 高亮最优 → 点行打开完整 run。  
5. 批量失败行可见错误；对比表增加指标列。  
6. 文案改为「vnpy CTA 日 K 回测」。

## 错误处理

| 场景 | 行为 |
|------|------|
| 日 K 不足 / 无数据 | `status=failed`，文案明确；UI 链 Ops |
| 参数非法 / 网格过大 | API 400 |
| 单票引擎异常 | 失败行 + job `success=false` |
| 批量部分失败 | 成功/失败均落库；job 含 `failed_count` |
| 子进程超时 | 默认单票 120s（`BACKTEST_TASK_TIMEOUT_S`）；记失败 |
| worker 无 vnpy | 启动或首任务明确失败；**禁止**回退薄引擎 |

## 部署

- API 镜像：不加 vnpy。  
- 新服务 `backtest-worker`：可选依赖组 `backtest`（`vnpy`、`vnpy_ctastrategy` 等）；compose 增加服务，只消费 `backtest` 队列。  
- 环境变量：`BACKTEST_SUBPROCESS`（批量/优化强制子进程）、`BACKTEST_MAX_WORKERS`、`BACKTEST_TASK_TIMEOUT_S`；PG/Redis 与现网一致。

## 测试

1. 映射与转换纯函数测试（可不装 vnpy）。  
2. 策略单元：金叉/死叉、T+1、整手（合成 K 线）。  
3. 引擎集成：`pytest` mark `vnpy`（CI 可选安装）。  
4. API：400 校验与 enqueue payload（mock）。  
5. 不强制与旧薄引擎数值回归一致。

## 验收标准

- [ ] 单票 / 批量走 vnpy；UI 可见完整指标与费用参数  
- [ ] 优化网格可跑；试次表与最优可见  
- [ ] 失败可诊断；缺 K 导向 Ops  
- [ ] API 镜像无 vnpy；backtest-worker 有 vnpy  
- [ ] 不改 zak；不 import `vnpy_ashare`  
- [ ] `./scripts/check.sh` 绿（vnpy 集成测可按 mark 跳过或分 job）

## 模块边界

| 路径 | 职责 |
|------|------|
| `app/strategies/cta/` | A 股 CTA 模板 + DoubleMa |
| `app/services/backtest_vnpy.py` | 引擎编排、history 注入、stats 映射 |
| `app/services/backtest_optimize.py` | 网格展开与目标排序 |
| `app/services/backtest_repo.py` | 持久化演进（status/params/engine） |
| `app/worker/tasks_backtest.py` | ARQ 任务；批量/优化子进程入口 |
| `app/api/v1/backtest.py` | REST 扩展 |
| `frontend/src/views/BacktestView.vue` | UI 加厚 |
| 删除/停用 | 生产路径对 `run_double_ma` 的调用 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| vnpy 依赖重、与 API 耦合 | 独立 worker 镜像 |
| 引擎全局状态串扰 | 批量/优化子进程 |
| A 股规则与桌面不完全一致 | 自研模板对齐语义；文档标明非 1:1 桌面包 |
| PyPI vnpy 版本漂移 | 锁版本；集成测钉版本 |
| 旧回测结果不可比 | UI/文档注明 `engine`；历史行保留 |

## 后续（明确不在本轮）

- 第二策略、分钟线  
- 与策略看盘共用同一信号实现  
- GA 优化、组合回测  
- 进程外调用桌面 zak CLI（曾评估的旁路方案 C）
