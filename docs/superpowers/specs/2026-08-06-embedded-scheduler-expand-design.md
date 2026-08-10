# 内嵌调度扩到全部可跑 Job 设计

日期：2026-08-06  
状态：已批准（方案 1：通用化内嵌调度器）  
范围：仅 zak2；不改 zak / vnpy-*

## 目标

- 内嵌 APScheduler 调度全部 `RUNNABLE_JOB_IDS`（与 Ops 手动跑共用同一套 runner）。
- 选股定时使用环境变量 `SCHEDULER_SCREEN_USER_ID`；未配置则跳过选股 job 并打日志。
- Ops 仅开关；cron 用内置默认，可被 `system.scheduler_config` 覆盖；不做 Web 改点钟 UI。
- 总开关：`EMBEDDED_SCHEDULER_ENABLED`（默认 true）；兼容旧 `BARS_SCHEDULER_ENABLED`。

## 非目标

- 多实例选主 / 分布式锁
- 调度尚未可跑的桌面 job（行情采集、全市场首下等）
- Web 编辑 cron / 配方 UI（配方继续读 config 中已有 `recipe_id` / `top_n`）
- 交易时段硬校验（定时触发即可跑；与现网手动 force 语义一致）

## 架构

1. 将 `bars_scheduler.py` 升格为 `embedded_scheduler.py`（`main` lifespan 改启停新模块；可删旧文件或留薄 re-export）。
2. 单一 `BackgroundScheduler`（时区 `Asia/Shanghai`）。
3. Runner 映射与 `ops.py` 的 `_RUNNERS` **同源**（抽到公共模块，例如 `ops_runners.py`，避免双份维护）。
4. 触发路径：总开关 → 读 config `enabled` →（若为选股）校验 `SCHEDULER_SCREEN_USER_ID` → 调 runner → 日志；runner 已写的 `last_run` meta 不额外破坏。
5. Settings：
   - `embedded_scheduler_enabled: bool = True`（env `EMBEDDED_SCHEDULER_ENABLED`）
   - `scheduler_screen_user_id: str = ""`（env `SCHEDULER_SCREEN_USER_ID`）
   - 保留 `bars_scheduler_enabled`（兼容旧 env）。
   - **生效总开关**（写死）：`embedded_scheduler_enabled and bars_scheduler_enabled`（任一为 false 则不启动；两默认均为 true，旧 `.env` 只关 `BARS_SCHEDULER_ENABLED` 仍生效）。

## 默认 cron（Asia/Shanghai；config 可覆盖）

| job_id | 默认 |
|--------|------|
| `sync_trade_calendar` | 周一 07:50（`cron_day_of_week=mon`） |
| `sync_sector_flow_daily` | 工作日 17:45（`mon-fri`） |
| `sync_limit_list` | 工作日 17:50 |
| `screen_post_close` | 工作日 18:00 |
| `fill_watchlist_bars` | 工作日 18:00 |
| `batch_fill_stale` | 工作日 18:30 |
| `purge_stale_cache` | 工作日 19:15 |
| `screen_intraday` | 工作日小时列表 `10,14`，分钟 `2`（读 `cron_hours` / `cron_minute_intraday`，缺省用该默认） |

其余工作日 job 若 config 未写 `cron_day_of_week`，默认 `mon-fri`。

## 互斥（写死）

- 同 job：`max_instances=1` + 进程内非阻塞锁。
- 日 K：`batch_fill_stale` 运行中则跳过 `fill_watchlist_bars`（保持现行为）。
- 其它 job：彼此不互斥；依赖靠默认时刻错开。

## 选股用户

- 环境变量 `SCHEDULER_SCREEN_USER_ID`（字符串用户 id）。
- 未配置或空：跳过 `screen_intraday` / `screen_post_close` 的定时执行，warning 日志；不影响其它 job；Ops **手动**跑仍用当前登录用户（现行为不变）。

## 错误与降级

| 情况 | 行为 |
|------|------|
| 总开关关 | 不启动 scheduler |
| job `enabled=false` | 到点跳过 |
| 选股无 screen user | 跳过该次 |
| runner 抛错 / `success=false` | 记日志；沿用 runner 的 meta；不拖垮进程 |
| 无 Tushare token | 沿用现 runner 失败文案 |
| 多 API 副本 | 文档注明可能双跑 |

## Ops / 前端

- 任务表：可跑行继续开关 + 立即跑；cron 字段只读展示（盘中可展示 `cron_hours`）。
- 文案：说明内嵌调度覆盖全部可跑 job；选股定时依赖 `SCHEDULER_SCREEN_USER_ID`。
- 不新增改点钟 UI。

## 配置与文档

- `.env.example`：`EMBEDDED_SCHEDULER_ENABLED`、`SCHEDULER_SCREEN_USER_ID`；注明旧 `BARS_SCHEDULER_ENABLED` 兼容。
- 更新 `docs/gap-vs-desktop.md`、`docs/smoke-checklist.md`。

## 测试

- mock，不打真网。
- 注册表覆盖全部 `RUNNABLE_JOB_IDS`。
- 总开关关 / `enabled=false` → 不执行。
- 选股无 user → skip；有 user → 调到 runner。
- 日 K 互斥仍成立。
- 默认 cron 解析（含 intraday 多小时）。

## 验收

1. 总开关开启后，8 个可跑 job 均可按 enabled 定时触发（测可用直接调内部 `_run_job` / 注入）。
2. Ops 开关持久化与手动跑行为不变。
3. 全量 pytest + `npm run build` 绿。
