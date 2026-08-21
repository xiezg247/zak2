# Task 3 Report: 拆除 screener 域兼容壳

## Status
✅ Done（Wave B Task 3 完成）

## Commits
- `8f9abf4` refactor(domains): 拆除 screener 域兼容壳

## 改动内容

### 删除 shim（14 个文件）
- `app/services/screener/` 整目录：`__init__.py` + engine/hard_filters/leader_screen/pattern_rules/pattern_screen/presets/recipe_weights/reference_peer/resonance_screen.py（共 10 个）
- `app/schemas/screener.py`
- `app/repositories/screener.py`
- `app/api/v1/screener.py`

### 改消费者
- `app/schemas.screener` → `app.domains.screener.schemas`：
  - `app/services/ops/arq_jobs.py`、`app/api/v1/ops.py`、`app/api/v1/jobs.py`（JobOut）
  - `app/services/ops/auto_screen.py`（RecipeRunRequest）
  - `app/worker/tasks_screener.py`
  - tests：test_recipe_weights / test_pattern_screen / test_suspend_filter / test_hard_filters_resolve / test_zak_copy_closeout / test_resonance_screen / test_presets_d / test_reference_peer / test_ops_jobs_aggregate / test_ops_enqueue / test_leader_screen / test_engine
- `app.services.screener.*` → `app.domains.screener.*`（模块名不变）：
  - `app/services/ops/auto_screen.py`（engine.run_recipe_screen）
  - `app/worker/tasks_screener.py`（engine / pattern_screen / reference_peer）
  - tests：test_recipe_weights / test_pattern_screen / test_suspend_filter / test_hard_filters_resolve / test_resonance_screen / test_presets_b / test_presets_d / test_reference_peer / test_ops_auto_screen / test_radar_leader_collector_copy / test_pattern_rules（含 line 59 `import app.domains.screener.pattern_rules as rules`）/ test_leader_screen / test_engine
- `app.repositories.screener` → `app.domains.screener.repository`：
  - tests patch 目标：test_auto_schedule_task.py（4 处）、test_ops_auto_screen.py（8 处）
  - `from app.repositories import screener as repo` → `from app.domains.screener import repository as repo`：`app/services/ops/auto_screen.py`、`app/worker/tasks_screener.py`、`tests/test_screener_result_compat.py`
  - **额外发现**：`app/services/ai/ai_read_tools.py` 以 `from app.repositories import screener as screener_repo` 引用 shim（brief 清单外的隐式消费者），一并改走 `app.domains.screener.repository`
- `app/api/v1/__init__.py`：`from app.domains.screener.router import router as screener_router`，`api_router.include_router(screener_router)`，并从 `from app.api.v1 import (...)` 元组移除 screener

### 约束保持
- REST 路径、`SCREENER_FUNCS` / job_id、算法均未改动；`app/models/screener.py`、`app/services/market/tushare_screener.py` 保留（非 shim）；未删其它域 shim。

## Tests
- 残留扫描：`rg "app.services.screener|app.schemas.screener|app.repositories.screener|app.api.v1.screener|from app.repositories import.*screener" app tests --glob '*.py'` → **零命中**
- 全量：`cd backend && uv run pytest -q --tb=short` → **713 passed**

## Concerns
- 无。brief 消费者清单之外唯一需处理的隐式消费者为 `app/services/ai/ai_read_tools.py`（多行 `from app.repositories import (screener as screener_repo)` 风格，非点路径 rg 可捕获），已修复并全量验证。
