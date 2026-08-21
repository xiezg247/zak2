### Task 3: screener 拆壳

**Files 删除（14 个 shim）：**
- `app/services/screener/` 整目录（`__init__.py` + engine/hard_filters/leader_screen/pattern_rules/pattern_screen/presets/recipe_weights/reference_peer/resonance_screen.py）
- `app/schemas/screener.py`
- `app/repositories/screener.py`
- `app/api/v1/screener.py`

**改消费者（先改后删）：**

1. `app.schemas.screener` → `app.domains.screener.schemas`：
   - `app/services/ops/arq_jobs.py`（JobOut）
   - `app/services/ops/auto_screen.py`（RecipeRunRequest）
   - `app/api/v1/ops.py`、`app/api/v1/jobs.py`（JobOut）
   - `app/worker/tasks_screener.py`
   - tests：test_recipe_weights / test_pattern_screen / test_suspend_filter / test_hard_filters_resolve / test_zak_copy_closeout / test_resonance_screen / test_presets_d / test_reference_peer / test_ops_jobs_aggregate / test_ops_enqueue / test_leader_screen / test_engine / test_auto_schedule_task
2. `app.services.screener.*` → `app.domains.screener.*`（模块名不变）：
   - `app/services/ops/auto_screen.py`（engine.run_recipe_screen）
   - `app/worker/tasks_screener.py`（engine / pattern_screen / reference_peer）
   - tests：test_recipe_weights / test_pattern_screen / test_suspend_filter / test_hard_filters_resolve / test_resonance_screen / test_presets_b / test_presets_d / test_reference_peer / test_ops_auto_screen / test_radar_leader_collector_copy / test_pattern_rules / test_leader_screen / test_engine
3. `app.repositories.screener` → `app.domains.screener.repository`（tests patch 目标）：
   - test_auto_schedule_task.py（4 处 patch）、test_ops_auto_screen.py（8 处 patch）
4. `app/api/v1/__init__.py`：screener router 直连 `from app.domains.screener.router import router as screener_router`，并从 `from app.api.v1 import (...)` 元组移除 screener。

**注意：**
- `services/ops/arq_jobs.py` 的 `SCREENER_FUNCS` 等常量与 job_id 名不变。
- `test_pattern_rules.py:59` 的 `import app.services.screener.pattern_rules as rules` → `import app.domains.screener.pattern_rules as rules`。
- 删除后运行：
```bash
cd backend && rg "app.services.screener|app.schemas.screener|app.repositories.screener|app.api.v1.screener" app tests --glob '*.py'
```
必须零命中。

**测试：**
```bash
cd backend && uv run pytest -q --tb=short
```
全量绿才提交（预计 713+）。

**Commit**（简体中文 HEREDOC）：
`refactor(domains): 拆除 screener 域兼容壳`

**Report** → `/Users/xiezhigang/Projects/me/zak2/.worktrees/backend-domains-phase6/.superpowers/sdd/task-3-report.md`

**禁止：** 改 REST 路径/SCREENER_FUNCS/算法；改 domains 实现；删其它域 shim（market 属 Task 4）。
