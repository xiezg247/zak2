### Task 6: backtest + auto_schedules 拆壳

**Files 删除（14 个 shim）：**
- `app/services/backtest/` 整目录（backtest_bars/backtest_engine/backtest_map/backtest_optimize/backtest_settings/backtest_vnpy + `__init__.py`）
- `app/schemas/backtest.py`
- `app/repositories/backtest.py`
- `app/services/ops/auto_schedule.py`、`app/services/ops/auto_schedule_time.py`
- `app/schemas/auto_schedule.py`
- `app/repositories/auto_schedule.py`
- `app/api/v1/backtest.py`、`app/api/v1/auto_schedules.py`

**改消费者（先改后删）：**

**backtest 组：**
1. `app.schemas.backtest` → `app.domains.backtest.schemas`：`app/worker/tasks_backtest.py`、tests（test_backtest_cta_medium_swing/cta_extra/profiles/cta_trend_ma/schemas/bars_interval）
2. `app.services.backtest.*` → `app.domains.backtest.*`（模块名不变）：`app/worker/tasks_backtest.py`（backtest_bars/backtest_optimize/backtest_settings）、`app/worker/backtest_subprocess.py`（lazy `from app.services.backtest.backtest_vnpy import run_cta_backtest`）、tests（test_backtest_engine/cta_medium_swing/cta_extra/vnpy_1m/profiles/api_validate/optimize/vnpy_engine/cta_trend_ma/bars_interval/map）
3. 仓库多行风格：
   - `app/services/ai/ai_tools.py:12`：`from app.repositories import backtest as backtest_repo` → `from app.domains.backtest import repository as backtest_repo`
   - `app/worker/tasks_backtest.py:17`：`from app.repositories import backtest as repo` → `from app.domains.backtest import repository as repo`
   - `tests/test_backtest_cta_trend_ma.py:34`：同上 `as repo`

**auto_schedules 组：**
4. `app.services.ops.auto_schedule` / `auto_schedule_time` → `app.domains.auto_schedules.auto_schedule` / `auto_schedule_time`：
   - `app/services/ops/embedded_scheduler.py:101`（lazy import）
   - tests：test_auto_schedule_poll.py（import + 5 处 patch）、test_auto_schedule_time.py、test_auto_schedule_task.py（import + patch 目标 `app.services.ops.auto_schedule.run_recipe_screen` / `.notify_delivery.deliver_text`）
5. `app.repositories.auto_schedule` → `app.domains.auto_schedules.repository`：test_auto_schedule_repo.py（import）、test_auto_schedule_task.py（3 处 patch）
6. `app/api/v1/__init__.py`：backtest/auto_schedules router 直连 `from app.domains.backtest.router import router as backtest_router`、`from app.domains.auto_schedules.router import router as auto_schedules_router`，从 `from app.api.v1 import (...)` 元组移除 backtest、auto_schedules。

**注意：** `auto_schedules` 域服务可能仍引用 `app.services.ops.*`（arq_jobs 等）——那是真实现保留，不改。ARQ job 名不变。

**删除后残留扫描必须零命中：**
```bash
cd backend && rg "app.services.backtest|app.schemas.backtest|app.repositories.backtest|app.services.ops.auto_schedule|app.schemas.auto_schedule|app.repositories.auto_schedule|app.api.v1.backtest|app.api.v1.auto_schedules" app tests --glob '*.py'
```

**测试：**
```bash
cd backend && uv run pytest -q --tb=short
```
全量绿才提交（预计 713+）。

**Commit**（简体中文 HEREDOC）：
`refactor(domains): 拆除 backtest/auto_schedules 域兼容壳`

**Report** → `/Users/xiezhigang/Projects/me/zak2/.worktrees/backend-domains-phase6/.superpowers/sdd/task-6-report.md`

**禁止：** 改 REST 路径/算法/ARQ job 名；改 domains 实现；改 `services/ops` 其余真实现文件（embedded_scheduler 仅改 lazy import 路径）。
