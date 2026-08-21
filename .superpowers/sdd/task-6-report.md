# Task 6 Report: backtest + auto_schedules 拆壳

## Status

✅ 完成（commit `0b1099d`）

## Commits

- `0b1099d` `refactor(domains): 拆除 backtest/auto_schedules 域兼容壳`

## Changes

**删除 15 个 shim 文件（git rm）：**

- `app/services/backtest/`（`__init__` + backtest_bars/backtest_engine/backtest_map/backtest_optimize/backtest_settings/backtest_vnpy）
- `app/schemas/backtest.py`、`app/repositories/backtest.py`
- `app/services/ops/auto_schedule.py`、`app/services/ops/auto_schedule_time.py`
- `app/schemas/auto_schedule.py`、`app/repositories/auto_schedule.py`
- `app/api/v1/backtest.py`、`app/api/v1/auto_schedules.py`

**改消费者（先改后删）：**

- `worker/tasks_backtest.py`：`app.repositories`→`app.domains.backtest.repository`（`as repo`）、schemas 与 backtest_bars/backtest_optimize/backtest_settings → `app.domains.backtest.*`
- `worker/backtest_subprocess.py`：lazy import `app.services.backtest.backtest_vnpy` → `app.domains.backtest.backtest_vnpy`
- `services/ai/ai_tools.py:12`：`from app.repositories import backtest as backtest_repo` → `from app.domains.backtest import repository as backtest_repo`
- `tests/test_backtest_cta_trend_ma.py:34`：同上 `as repo`
- 其余 12 个 backtest 测试文件的 schemas/service import 全部改 `app.domains.backtest.*`
- `services/ops/embedded_scheduler.py:101`：lazy import → `app.domains.auto_schedules.service.poll_due_tasks`
- `worker/tasks_auto_schedule.py`：`from app.services.ops import auto_schedule as ops_auto_schedule` → `from app.domains.auto_schedules import service as ops_auto_schedule`（模块别名名保留，`test_worker_task_returns_dict` patch 目标不变）
- `test_auto_schedule_{poll,time,task,repo}.py`：import 与 patch 目标全部改 `app.domains.auto_schedules.service/repository/auto_schedule_time`
- `app/api/v1/__init__.py`：backtest/auto_schedules router 直连 `app.domains.{backtest,auto_schedules}.router`，从 `from app.api.v1 import (...)` 元组移除

**映射说明：** `app.services.ops.auto_schedule`（sys.modules 别名到域 service）→ `app.domains.auto_schedules.service`（域内为 `service.py`，无 `auto_schedule.py` 模块）；`app.services.ops.auto_schedule_time` → `app.domains.auto_schedules.auto_schedule_time`。

**禁止项核验：** REST 路径/算法/ARQ job 名未改；domains 实现未动；`services/ops` 其余真实现文件仅 embedded_scheduler 改 lazy import 路径。

## Tests

- 残留扫描：brief 指定的 8 组旧路径 rg 扫描零命中
- 全量回归：`uv run pytest -q --tb=short` → **713 passed** ✅
- import 冒烟：`import app.main / app.worker.tasks_backtest / tasks_auto_schedule / backtest_subprocess` 通过

## Concerns

- brief 消费者清单未含 `worker/tasks_auto_schedule.py`，但该文件以 `from app.services.ops import auto_schedule` 引用 shim（非点号路径，扫描不会命中），删除 shim 后必须同步改指域 service，否则 `test_auto_schedule_task.py` 导入即失败；已一并修正并保留 `ops_auto_schedule` 别名。
