# vnpy CTA 回测加深 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 zak2 回测主路径切换为独立 backtest-worker 内嵌的 PyPI vnpy CTA 引擎，并交付费用参数、完整统计、网格优化与 UI。

**Architecture:** API 只校验入队（队列 `zak2:arq:backtest`）；`backtest-worker` 装 vnpy，从 PG `dbbardata` 注入 `history_data` 后跑 `BacktestingEngine`；批量/优化用子进程隔离；结果落 `app.backtest_runs`（含 engine/status/params）。

**Tech Stack:** FastAPI、ARQ、PostgreSQL、PyPI `vnpy` + `vnpy_ctastrategy`、Vue 3、pytest、Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-14-vnpy-backtest-deepen-design.md`

## Global Constraints

- 只改 zak2；不改 zak 仓库代码
- **禁止** `import vnpy_ashare` 及其它 zak 包
- **仅** backtest-worker 允许 `import vnpy` / `vnpy_ctastrategy`；API 镜像不加 vnpy
- 行情：PG `public.dbbardata` → `BarData` → `engine.history_data`；**不**调用依赖 `~/.vntrader` 的 `load_data()`
- 默认费用：`rate=0.00045`，`slippage=0.0`，`stamp_duty=0.0005`（仅卖出）；`size=1`，`pricetick=0.01`
- 优化网格硬顶 **64** 组；首期仅日 K + `double_ma`
- **禁止**静默回退旧薄引擎 `run_double_ma`
- commit message 简体中文：`<type>(<scope>): <简述>`
- 最终 `./scripts/check.sh` 绿；vnpy 集成测用 `@pytest.mark.vnpy`，默认 check 可跳过未安装环境

## File map

| 路径 | 职责 |
|------|------|
| `backend/alembic/versions/010_backtest_runs_vnpy_columns.py` | 加 `engine`/`params_json`/`status`/`error_message` |
| `backend/app/models/backtest.py` | ORM 新列 |
| `backend/app/schemas/backtest.py` | 请求费用字段、Optimize 请求/响应、RunOut 扩展 |
| `backend/app/services/backtest_bars.py` | 日 K 加载（从 engine 迁出）+ 转 dict（无 vnpy） |
| `backend/app/services/backtest_optimize.py` | 网格展开、校验、排序 |
| `backend/app/services/backtest_map.py` | vnpy stats/trades/daily → 落库 dict（尽量无硬依赖） |
| `backend/app/strategies/cta/ashare_template.py` | 整手/T+1 薄模板 |
| `backend/app/strategies/cta/double_ma.py` | DoubleMa CTA |
| `backend/app/strategies/cta/registry.py` | strategy id → class |
| `backend/app/services/backtest_vnpy.py` | 引擎编排（**依赖 vnpy**） |
| `backend/app/services/backtest_repo.py` | execute/save 走 vnpy；失败行；optimize 聚合 |
| `backend/app/services/backtest_engine.py` | 保留 STRATEGIES/PROFILES；删除生产 `run_double_ma` 或迁测试 |
| `backend/app/worker/settings_backtest.py` | 仅回测 functions + `queue_name=zak2:arq:backtest` |
| `backend/app/worker/settings.py` | **移除** backtest functions |
| `backend/app/worker/tasks_backtest.py` | single/batch/optimize + 子进程 |
| `backend/app/worker/backtest_subprocess.py` | 子进程入口 `run_one_payload` |
| `backend/app/services/arq_jobs.py` | backtest 入队改用 backtest 队列；注册 optimize |
| `backend/app/core/settings.py` | `arq_backtest_queue_name`、超时/并发 |
| `backend/app/api/v1/backtest.py` | optimize API、校验 |
| `backend/pyproject.toml` / `uv.lock` | optional-dependencies `backtest` |
| `backend/Dockerfile` | build-arg 安装 backtest extras |
| `docker-compose.yml` | `backtest-worker` 服务 |
| `scripts/arq_backtest_worker.sh` / `scripts/dev.sh` | 本地启动 |
| `frontend/src/api/backtest.ts` | 类型与 optimize API |
| `frontend/src/views/BacktestView.vue` | 费用区、厚指标、优化 Tab |
| `backend/tests/test_backtest_*.py` | 网格/映射/API/策略；`test_backtest_vnpy_engine.py` mark vnpy |

---

### Task 1: 表结构 + ORM + Schema 扩展

**Files:**
- Create: `backend/alembic/versions/010_backtest_runs_vnpy_columns.py`
- Modify: `backend/app/models/backtest.py`
- Modify: `backend/app/schemas/backtest.py`
- Test: `backend/tests/test_backtest_schemas.py`

**Interfaces:**
- Produces: ORM 字段 `engine: str | None`, `params_json: str`, `status: str`, `error_message: str | None`
- Produces: `BacktestRunRequest` 增加 `rate`/`slippage`/`stamp_duty`（默认见 Global）
- Produces: `OptimizeBacktestRequest`（`vt_symbol`, dates, capital, fees, `space: dict[str, list[int]]`, `objective: str = "sharpe_ratio"`）
- Produces: `OptimizeSummaryOut`（`batch_id`, `objective`, `best: BacktestRunOut | None`, `runs: list[BacktestRunOut]`）
- Produces: `BacktestRunOut` 增加 `engine`/`status`/`error_message`/`params`（解析自 params_json）
- Produces: `StrategyInfo.engine: str = "vnpy"`

- [ ] **Step 1: 写 schema 校验测试**

```python
# backend/tests/test_backtest_schemas.py
from app.schemas.backtest import BacktestRunRequest, OptimizeBacktestRequest

def test_run_request_fee_defaults():
    r = BacktestRunRequest(vt_symbol="600519.SSE")
    assert r.rate == 0.00045
    assert r.slippage == 0.0
    assert r.stamp_duty == 0.0005

def test_optimize_request_accepts_space():
    o = OptimizeBacktestRequest(
        vt_symbol="600519.SSE",
        space={"fast_window": [5, 10], "slow_window": [20, 30]},
    )
    assert o.objective == "sharpe_ratio"
```

- [ ] **Step 2: 跑测试确认失败（字段尚无）**

Run: `cd backend && uv run pytest tests/test_backtest_schemas.py -q`  
Expected: FAIL（ImportError 或 validation）

- [ ] **Step 3: 扩展 schemas + model**

`BacktestRun` 新增列（Text/可空按 spec）。`BatchBacktestRequest.symbols` 的 `max_length` 改为 50。

- [ ] **Step 4: 写 migration `010_backtest_runs_vnpy_columns.py`**

```python
"""backtest_runs vnpy columns"""
revision = "010_backtest_runs_vnpy_columns"
down_revision = "009_create_public_bars"

def upgrade() -> None:
    op.execute("ALTER TABLE app.backtest_runs ADD COLUMN IF NOT EXISTS engine TEXT")
    op.execute("ALTER TABLE app.backtest_runs ADD COLUMN IF NOT EXISTS params_json TEXT NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE app.backtest_runs ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'success'")
    op.execute("ALTER TABLE app.backtest_runs ADD COLUMN IF NOT EXISTS error_message TEXT")

def downgrade() -> None:
    op.execute("ALTER TABLE app.backtest_runs DROP COLUMN IF EXISTS error_message")
    op.execute("ALTER TABLE app.backtest_runs DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE app.backtest_runs DROP COLUMN IF EXISTS params_json")
    op.execute("ALTER TABLE app.backtest_runs DROP COLUMN IF EXISTS engine")
```

- [ ] **Step 5: 再跑 schema 测试通过**

Run: `cd backend && uv run pytest tests/test_backtest_schemas.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/010_backtest_runs_vnpy_columns.py \
  backend/app/models/backtest.py backend/app/schemas/backtest.py \
  backend/tests/test_backtest_schemas.py
git commit -m "$(cat <<'EOF'
feat(backtest): 扩展回测表与请求字段以支持 vnpy

为引擎标识、参数快照、失败状态与费用/优化请求留位。
EOF
)"
```

---

### Task 2: 网格展开与排序（纯函数）

**Files:**
- Create: `backend/app/services/backtest_optimize.py`
- Test: `backend/tests/test_backtest_optimize.py`

**Interfaces:**
- Produces:
  - `MAX_OPTIMIZE_COMBOS = 64`
  - `def expand_ma_grid(space: dict[str, list[int]]) -> list[dict[str, int]]`  
    只认 `fast_window`/`slow_window`；过滤 `fast >= slow`；超 64 抛 `ValueError`（API 再转 400）
  - `def pick_best(runs: list[dict], *, objective: str) -> dict | None`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from app.services.backtest_optimize import expand_ma_grid, pick_best

def test_expand_filters_fast_ge_slow():
    combos = expand_ma_grid({"fast_window": [5, 20], "slow_window": [10, 20]})
    assert {"fast_window": 5, "slow_window": 10} in combos
    assert {"fast_window": 20, "slow_window": 10} not in combos

def test_expand_rejects_over_64():
    with pytest.raises(ValueError, match="64"):
        expand_ma_grid({
            "fast_window": list(range(2, 12)),
            "slow_window": list(range(20, 30)),
        })  # 10*10=100 > 64

def test_pick_best_sharpe():
    best = pick_best(
        [{"sharpe_ratio": 0.1}, {"sharpe_ratio": 1.2}, {"sharpe_ratio": None}],
        objective="sharpe_ratio",
    )
    assert best["sharpe_ratio"] == 1.2
```

- [ ] **Step 2: 跑测失败 → 实现 → 跑通 → Commit**

```bash
git add backend/app/services/backtest_optimize.py backend/tests/test_backtest_optimize.py
git commit -m "$(cat <<'EOF'
feat(backtest): 参数网格展开与最优选取

支撑优化回测的组合生成与目标排序。
EOF
)"
```

---

### Task 3: 日 K 加载迁出 + 无 vnpy 的 bar/统计映射

**Files:**
- Create: `backend/app/services/backtest_bars.py`（迁 `load_daily_bars` + `Bar` dataclass）
- Create: `backend/app/services/backtest_map.py`
- Modify: `backend/app/services/backtest_engine.py`（从 bars 再导出或删重复，避免双份）
- Test: `backend/tests/test_backtest_map.py`

**Interfaces:**
- Produces: `load_daily_bars(...)` 仍返回内部 `Bar` 列表；不足 30 根继续 HTTP 400（或改为可被 repo 捕获的领域异常，文案含「日 K」）
- Produces: `bars_to_records(bars) -> list[dict]`（datetime/OHLCV 可 JSON 序列化，供子进程）
- Produces: `map_vnpy_statistics(stats: dict, *, trades, daily_df_or_rows) -> dict`  
  输出落库结构：
  ```python
  {
    "total_return": float | None,  # 与列一致；注意 vnpy 常为小数或已含 %，统一成「百分比数值」与现 UI 兼容（现薄引擎为 %）
    "max_drawdown": float | None,
    "sharpe_ratio": float | None,
    "trade_count": int | None,
    "statistics": {**stats, "annual_return": ..., "return_std": ..., "win_rate": ...},
    "equity_curve": [{"datetime": "...", "equity": ...}],
    "trades": [...],
  }
  ```
  实现时对照一次真实 `calculate_statistics` 键名；写适配层把 `%` 字符串转 float。

- [ ] **Step 1: 用伪造 stats dict 测 map（不 import vnpy）**

```python
from app.services.backtest_map import map_vnpy_statistics

def test_map_strips_percent_and_builds_curve():
    out = map_vnpy_statistics(
        {"total_return": "12.5%", "max_drawdown": "-3.2%", "sharpe_ratio": 1.1, "total_trade_count": 4},
        trades=[],
        daily_rows=[{"date": "2024-01-02", "balance": 101000}],
    )
    assert out["total_return"] == 12.5
    assert out["trade_count"] == 4
    assert out["equity_curve"][0]["equity"] == 101000
```

- [ ] **Step 2: 实现 map + 迁 bars → 测试绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(backtest): 拆出日 K 加载与 vnpy 结果映射

为无 vnpy 的单测与子进程载荷做准备。
EOF
)"
```

---

### Task 4: CTA 策略（依赖 vnpy，可 mark）

**Files:**
- Create: `backend/app/strategies/cta/__init__.py`
- Create: `backend/app/strategies/cta/ashare_template.py`
- Create: `backend/app/strategies/cta/double_ma.py`
- Create: `backend/app/strategies/cta/registry.py`
- Test: `backend/tests/test_backtest_cta_double_ma.py`

**Interfaces:**
- Produces: `AShareCtaTemplate(CtaTemplate)`：`round_volume` 整手 100；`buy_stock`/`sell_stock`（T+1：记录买入日，卖出拒绝当日仓）
- Produces: `DoubleMaStrategy`：参数 `fast_window`/`slow_window`/`trade_volume`；金叉买死叉卖（对齐桌面语义）
- Produces: `registry.get_strategy_class("double_ma") -> type`
- `stamp_duty`：不在策略内重复扣佣金；由 Task 5 引擎侧处理卖出印花税

- [ ] **Step 1: pyproject 增加 optional `backtest` 并 uv lock**

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.24.0"]
backtest = [
  "vnpy>=3.9.0,<4",
  "vnpy-ctastrategy>=3.9.0,<4",
]
```

Run: `cd backend && uv lock && uv sync --extra dev --extra backtest`

若包名在 PyPI 为 `vnpy_ctastrategy`，以 `uv add --optional backtest vnpy vnpy_ctastrategy` 为准并锁版本。

- [ ] **Step 2: 实现策略 + registry**

参考桌面 `/Users/xiezhigang/Projects/me/zak/strategies/double_ma_strategy.py` **只读**语义，禁止 import。

- [ ] **Step 3: 单元测（有 vnpy 才跑）**

```python
import pytest

pytest.importorskip("vnpy_ctastrategy")

@pytest.mark.vnpy
def test_registry_double_ma():
    from app.strategies.cta.registry import get_strategy_class
    cls = get_strategy_class("double_ma")
    assert cls.__name__ == "DoubleMaStrategy"
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(backtest): 增加 A 股 CTA 双均线策略

在 zak2 内重写整手与 T+1 语义，供 vnpy 引擎加载。
EOF
)"
```

---

### Task 5: vnpy 引擎编排 + repo 切换

**Files:**
- Create: `backend/app/services/backtest_vnpy.py`
- Modify: `backend/app/services/backtest_repo.py`
- Modify: `backend/app/services/backtest_engine.py`（STRATEGIES 加 `engine: "vnpy"`；删除生产对 `run_double_ma` 的依赖）
- Test: `backend/tests/test_backtest_vnpy_engine.py`（mark vnpy）
- Modify: `backend/tests/test_backtest_engine.py`（改为测 STRATEGIES/PROFILES 或删薄引擎测）

**Interfaces:**
- Produces:
  ```python
  def run_cta_backtest(
      bar_records: list[dict],
      *,
      vt_symbol: str,
      strategy_id: str,
      setting: dict,
      start: str,
      end: str,
      capital: float,
      rate: float,
      slippage: float,
      stamp_duty: float,
      size: int = 1,
      pricetick: float = 0.01,
  ) -> dict:  # map_vnpy_statistics 输出；无数据/异常向上抛
  ```
- 内部：`BacktestingEngine` → `set_parameters` → `add_strategy` → 将 records 转为 `BarData` 填入 `history_data` → **跳过** `load_data` → `run_backtesting` → `calculate_result` → `calculate_statistics(output=False)`
- 印花税：安装后阅读 `BacktestingEngine` 成交费用计算点，优先子类覆盖「卖出加 stamp_duty * turnover」；若无稳定钩子，则在 `map` 后把估算 `stamp_duty_total` 写入 `statistics`，并在模块 docstring 标明引擎内未扣税（须在实现时二选一写死，**不得**留 TBD）
- `execute_single`：catch 缺 K/引擎错误 → `save_run(..., status="failed", error_message=..., result 空指标)`；成功 `engine="vnpy"`，`params_json` 含 setting+fees
- 未知 strategy → 400/501

- [ ] **Step 1: 合成 60 根日 K 的集成测（需 vnpy）**

金叉死叉可交易；断言 `status` 成功路径返回 `sharpe_ratio is not None` 或 `trade_count >= 0`。

- [ ] **Step 2: 实现 `backtest_vnpy` + 改 `execute_single`**

- [ ] **Step 3: 无 vnpy 时 `execute_single` 必须明确失败（ImportError → 清晰错误），禁止调用 `run_double_ma`**

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(backtest): 主路径切换为 vnpy CTA 引擎

从 PG 注入日 K，落库完整统计并记录失败状态。
EOF
)"
```

---

### Task 6: 独立队列、子进程、optimize 任务

**Files:**
- Modify: `backend/app/core/settings.py` — `arq_backtest_queue_name: str = "zak2:arq:backtest"`；`backtest_task_timeout_s: int = 120`；`backtest_max_workers: int = 4`
- Create: `backend/app/worker/settings_backtest.py`
- Modify: `backend/app/worker/settings.py` — 去掉 `run_backtest_*`
- Create: `backend/app/worker/backtest_subprocess.py` — `if __name__` 可读 stdin JSON，调 `run_cta_backtest`，stdout JSON
- Modify: `backend/app/worker/tasks_backtest.py` — batch/optimize 用 `subprocess.run`/`ProcessPool`；single 默认同进程（`BACKTEST_SUBPROCESS=1` 可强制）
- Modify: `backend/app/services/arq_jobs.py` — `BACKTEST_FUNCS` 增 `backtest.optimize`；`enqueue_app_job` 对 backtest kind 使用 `arq_backtest_queue_name`
- Test: `backend/tests/test_backtest_arq_enqueue.py`（mock pool，断言 queue_name 与 function）

**Interfaces:**
- Produces: `async def run_backtest_optimize(ctx, *, user_id, payload, batch_id) -> dict`
- Batch：每标的失败调用 `save_run` failed 行；返回 `failed_count`
- Optimize：`expand_ma_grid` → 每组 setting 跑一次 → `source="optimize"`

- [ ] **Step 1: enqueue 测试断言队列名**

```python
# mock ArqRedis.enqueue_job，检查 _queue_name == "zak2:arq:backtest"
```

- [ ] **Step 2: 实现 worker 拆分与子进程 → 测过 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(backtest): 独立回测队列与子进程隔离

批量与优化不再与 Ops worker 抢同一执行面。
EOF
)"
```

---

### Task 7: API — 校验与 optimize 端点

**Files:**
- Modify: `backend/app/api/v1/backtest.py`
- Modify: `backend/app/services/backtest_repo.py` — `summarize_optimize(db, user_id, batch_id, objective)`
- Test: `backend/tests/test_backtest_api_validate.py`（FastAPI TestClient 或纯函数校验抽出）

**Interfaces:**
- `POST /optimize` → 校验 grid → `enqueue` kind `backtest.optimize` → `JobAccepted`
- `GET /optimize/{batch_id}` → `OptimizeSummaryOut`
- `POST /runs`：若 `fast_window >= slow_window` → 400
- strategies 响应带 `engine: "vnpy"`

- [ ] **Step 1: 校验测试（超 64、fast>=slow）→ 实现 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(backtest): 开放参数优化 API 与入参校验

网格超限与均线约束在入队前拒绝。
EOF
)"
```

---

### Task 8: Docker / 本地脚本

**Files:**
- Modify: `backend/Dockerfile` — `ARG INSTALL_BACKTEST=0`；若 1 则 `uv sync --frozen --no-dev --extra backtest`
- Modify: `docker-compose.yml` — 服务 `backtest-worker`：`build.args.INSTALL_BACKTEST=1`，`entrypoint: ["arq", "app.worker.settings_backtest.WorkerSettings"]`，环境变量同 DB/Redis
- Create: `scripts/arq_backtest_worker.sh`
- Modify: `scripts/dev.sh` — 并行启动 backtest worker
- Modify: `backend/app/worker/settings.py` 确认不再注册 backtest（避免误消费）

- [ ] **Step 1: 文档化 compose 构建命令并本地 `docker compose build backtest-worker` 能过（网络允许时）**

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore(backtest): 增加 backtest-worker 镜像与启动脚本

API 保持轻依赖，仅回测进程安装 vnpy。
EOF
)"
```

---

### Task 9: 前端加厚

**Files:**
- Modify: `frontend/src/api/backtest.ts`
- Modify: `frontend/src/views/BacktestView.vue`

**UI 要求（对照 spec）：**
- 文案：vnpy CTA 日 K 回测
- 可折叠费用区（rate/slippage/stamp_duty）
- 结果卡：年化/波动/胜率/盈亏比等（从 `statistics` 读，缺则隐藏）
- 成交「显示全部」
- mode 增加 `optimize`：space 输入（可用简单逗号分隔 fast/slow 列表）→ startOptimize → poll → 拉 `/optimize/{batch_id}`
- 批量对比显示 `status`/`error_message`

- [ ] **Step 1: 实现 API 客户端 + UI**

- [ ] **Step 2: `cd frontend && npm run build` 通过**

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(backtest): 回测页支持费用、厚指标与参数优化

对齐 vnpy CTA 回测结果的可读性与可复现性。
EOF
)"
```

---

### Task 10: 清理薄引擎 + 验收

**Files:**
- Delete or quarantine: `run_double_ma` 生产代码；更新/删除 `test_backtest_engine.py` 中依赖薄撮合的用例
- Modify: `docs/superpowers/specs/2026-08-14-vnpy-backtest-deepen-design.md` 状态 → `已批准`
- Modify: `docs/product-roadmap.md`（若有回测条目）简短标注引擎切换（可选，有则改）

- [ ] **Step 1: `rg "run_double_ma" backend` 应为测试或零引用**

- [ ] **Step 2: `./scripts/check.sh`**

Expected: pytest + frontend build 绿；`@pytest.mark.vnpy` 在无 extra 时 skip

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(backtest): 移除薄双均线生产路径

回测统一走 vnpy CTA，避免双引擎结果混淆。
EOF
)"
```

---

## Self-review

1. **Spec coverage:** 独立 worker/队列、PG 注入、CTA 双均线、费用默认、失败落库、optimize≤64、UI 加厚、不回退薄引擎、不改 zak — 均有对应 Task。  
2. **Placeholder scan:** 印花税实现要求 Task 5 在两种方案中写死一种，禁止 TBD。  
3. **Type consistency:** `source=optimize`、`batch_id`、队列名 `zak2:arq:backtest`、function `run_backtest_optimize` 前后一致。  
4. **风险:** 主 `arq-worker` 去掉 backtest 后，若未起 `backtest-worker`，回测任务会积压 — 在 `dev.sh`/compose 与 API 错误文案中体现依赖该服务。
