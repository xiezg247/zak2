# 后端 Phase 3（domains watchlist）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将自选 / 分组 / 持仓 / 信号面板迁入 `app.domains.watchlist`，把 ~513 行胖 router 拆成 service + 薄 router（目标 `<280` 行、零 `HTTPException`/零直连 Repository）；旧路径保留兼容壳。

**Architecture:** 沿用 Phase 1/2：schemas + repositories 入域并改 `AppError`；`enrich` / `WatchlistService` / `PositionsService` / `SignalPanelService` 承接编排；`strategy_board` 仍留 `services/strategy`（本 Phase 只经薄调用，不搬 600+ 行算法）；`trading_risk` 迁入本域；`/quotes` `/bars` 仍挂本 router（路径历史兼容）。

**Tech Stack:** FastAPI、SQLAlchemy、`AppError` handler、pytest。

**Spec:** [docs/superpowers/specs/2026-08-20-backend-architecture-refactor-design.md](../specs/2026-08-20-backend-architecture-refactor-design.md) Phase 3。

## Global Constraints

- 对外 REST 路径、JWT、Redis 键、ARQ job_id、响应 schema 字段不变
- commit subject/body 简体中文，格式 `<type>(<scope>): <简述>`
- domain router **禁止** import/实例化 `*Repository`；**禁止** `HTTPException`
- domain repository/service **禁止** FastAPI `HTTPException`（用 `AppError`）
- domain **禁止** import `app.api.v1`
- `get_current_user` 留 `app.api.deps`；`models` 不搬包
- **不迁** `services/strategy/strategy_board.py` 及 signal 启发式大文件（仅调用）
- 旧路径 `app.repositories.{watchlist,positions,signal_panel}`、`app.schemas.watchlist`、`app.services.plan.trading_risk`、`app.api.v1.watchlist` 保留 thin re-export

## File map（结束时）

| 路径 | 职责 |
|------|------|
| `core/errors.py` | 新增 `Conflict`(409)、`Unavailable`(503) |
| `domains/watchlist/schemas.py` | 自 `schemas/watchlist.py` |
| `domains/watchlist/repository.py` | 自 `repositories/watchlist.py` + AppError |
| `domains/watchlist/positions_repo.py` | 自 `repositories/positions.py` + AppError |
| `domains/watchlist/signal_panel_repo.py` | 自 `repositories/signal_panel.py` + AppError |
| `domains/watchlist/enrich.py` | 原 router `_enrich` / `_opt_*` |
| `domains/watchlist/service.py` | 列表/增删/分组/重排 |
| `domains/watchlist/positions.py` | 持仓 CRUD 编排 |
| `domains/watchlist/signal_panel.py` | 信号面板编排 |
| `domains/watchlist/trading_risk.py` | 自 `services/plan/trading_risk.py` |
| `domains/watchlist/market_views.py` | quotes / bars / fundamentals |
| `domains/watchlist/router.py` | 薄路由 |
| `api/v1/watchlist.py` | re-export |
| 旧 repositories/schemas/trading_risk | re-export |

---

### Task 1: 新增 `Conflict` / `Unavailable`

**Files:**
- Modify: `backend/app/core/errors.py`
- Modify: `backend/tests/test_app_errors.py`

**Interfaces:**
- `class Conflict(AppError): status_code = 409`
- `class Unavailable(AppError): status_code = 503`

- [ ] **Step 1: 写失败测试**

在 `test_app_errors.py` 增加 import、`/cf` `/ua` 路由与：

```python
def test_conflict_maps_409() -> None:
    resp = _client().get("/cf")
    assert resp.status_code == 409
    assert resp.json()["message"] == "已在自选中"

def test_unavailable_maps_503() -> None:
    resp = _client().get("/ua")
    assert resp.status_code == 503
    assert "Redis" in resp.json()["message"]
```

路由内分别 `raise Conflict("已在自选中")` / `raise Unavailable("Redis 不可用")`。

- [ ] **Step 2: 跑测确认失败** → Expected ImportError

- [ ] **Step 3: 实现两类** 追加到 `errors.py`

- [ ] **Step 4: 跑 `pytest tests/test_app_errors.py -v`** → PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(api): 新增 Conflict(409) 与 Unavailable(503)

供自选冲突与 Redis 不可用等 watchlist 语义映射。
EOF
)"
```

---

### Task 2: 迁 schemas/repos 并替换 HTTPException

**Files:**
- Create: `domains/watchlist/__init__.py`、`schemas.py`、`repository.py`、`positions_repo.py`、`signal_panel_repo.py`
- Replace: `schemas/watchlist.py`、`repositories/{watchlist,positions,signal_panel}.py` → re-export
- Modify: `tests/test_watchlist_groups.py`、`tests/test_positions.py`（HTTPException → AppError）
- Modify: `tests/test_signal_panel.py` 若断言 HTTPException

**映射：**

| 原 status | AppError |
|-----------|----------|
| 400 | `ValidationFailed` |
| 404 | `NotFound` |
| 409 | `Conflict` |
| 503 | `Unavailable`（本 Task 若仅在 router，可留 Task 3） |

- [ ] **Step 1: 搬迁并替换**

1. `schemas/watchlist.py` → `domains/watchlist/schemas.py`（原样）
2. `repositories/watchlist.py` → `domains/watchlist/repository.py`：改 schemas import 为域内；删 `HTTPException`；按表映射；保留公开类名 `WatchlistItemRepository`、`WatchlistGroupRepository`、`WatchlistGroupMemberRepository`、`resolve_symbol_pair`、常量
3. `positions.py` → `positions_repo.py`：同上；409「该标的已有持仓记录」→ `Conflict`
4. `signal_panel.py` → `signal_panel_repo.py`：同上

域内 schemas：`from app.domains.watchlist.schemas import ...`

- [ ] **Step 2: 兼容壳**

```python
# repositories/watchlist.py
from app.domains.watchlist.repository import *  # noqa: F403
# 或显式导出全部公开名（推荐显式，避免泄漏私有）

# repositories/positions.py
from app.domains.watchlist.positions_repo import PositionRepository, POSITION_MAX_ITEMS  # 按实际公开符号

# repositories/signal_panel.py
from app.domains.watchlist.signal_panel_repo import ...

# schemas/watchlist.py
from app.domains.watchlist.schemas import ...
```

打开原文件列出 `__all__` / 被外部 import 的符号，用显式 re-export（与 Phase 1 一致，优于 `import *`）。

查消费方：

```bash
rg "from app.repositories.(watchlist|positions|signal_panel)|from app.schemas.watchlist" backend -g '*.py'
```

- [ ] **Step 3: 更新测试**

`test_watchlist_groups.py` / `test_positions.py`：`pytest.raises(HTTPException)` → `Conflict`/`ValidationFailed`/`NotFound`；`ei.value.detail` → `ei.value.message`；可改为 `from app.domains.watchlist import repository as repo`。

- [ ] **Step 4: 跑测**

```bash
cd backend && uv run pytest \
  tests/test_app_errors.py \
  tests/test_watchlist_groups.py \
  tests/test_positions.py \
  tests/test_signal_panel.py \
  tests/test_watchlist_industry_enrich.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(watchlist): schemas/repos 迁入 domains 并改用 AppError

旧 repositories/schemas 路径保留兼容壳；分组与持仓测试改断言领域异常。
EOF
)"
```

---

### Task 3: enrich + services + 薄 router

**Files:**
- Create: `enrich.py`、`service.py`、`positions.py`、`signal_panel.py`、`trading_risk.py`、`market_views.py`、`router.py`
- Replace: `api/v1/watchlist.py` → re-export；`services/plan/trading_risk.py` → re-export
- Modify: 凡 patch `app.api.v1.watchlist` 的测试改为域路径（`rg "api.v1.watchlist" backend/tests`）

**Interfaces（WatchlistService 示例）：**

```python
class WatchlistService:
    @staticmethod
    def list_items(db, user_id, *, enrich: bool, group_id: str | None) -> list[WatchlistItemOut]: ...
    @staticmethod
    def add_item(db, user_id, body: WatchlistAddRequest) -> WatchlistItemOut: ...
    @staticmethod
    def reorder(...) -> list[WatchlistItemOut]: ...
    @staticmethod
    def remove_item(...) -> None:  # 失败 raise NotFound("不在自选中")
    # groups: list/create/rename/delete/reorder/add_member/batch/remove_member
```

`PositionsService`：`list/add/update/delete`（delete 找不到 → `NotFound`）  
`SignalPanelService`：`get/replace/add/remove`  
`market_views.get_quotes`：Redis 不可用 → `Unavailable("Redis 不可用")`  
`trading_risk.save_...`：`ValueError` → 在 service 包装为 `ValidationFailed`，或迁文件后在 save 内改抛

**router 规则：** 仅 `Depends` + 调上述 service + `ApiResponse`；行数目标 `<280`；无 `_enrich` 定义。

- [ ] **Step 1: 实现 enrich.py**

把现 `api/v1/watchlist.py` 中 `_opt_price`、`_opt_field`、`_enrich` 原样迁入，schemas/quotes import 用域内与 `app.services.market.*`。

- [ ] **Step 2: 实现 service 层**

按现 router 行为逐端点搬到 service；分组删除失败等 router 内 `if not ...: raise HTTPException` 改为 service 抛 `NotFound`。

- [ ] **Step 3: trading_risk 迁入**

复制 `services/plan/trading_risk.py` → `domains/watchlist/trading_risk.py`，schemas 改域内；`save` 内 `ValueError` 可保留并由 service 转 `ValidationFailed`，或直接改抛 `ValidationFailed`。旧路径 re-export。

- [ ] **Step 4: market_views**

实现 `list_quotes`、`get_fundamentals`、`get_bars`（逻辑来自现 router 尾部）。

- [ ] **Step 5: router + api 壳**

```python
# api/v1/watchlist.py
from app.domains.watchlist.router import router
__all__ = ["router"]
```

strategy-board 端点：

```python
data=StrategyBoardOut(**strategy_board.load_strategy_board(...))
```

notify-log：`from app.domains.content import notify_log`（或兼容壳 `app.services.content.notify_log`）。

- [ ] **Step 6: 检查与测试**

```bash
cd backend && wc -l app/domains/watchlist/router.py
(rg "HTTPException|Repository" app/domains/watchlist/router.py && exit 1 || echo ok)
uv run pytest \
  tests/test_watchlist_groups.py \
  tests/test_positions.py \
  tests/test_signal_panel.py \
  tests/test_watchlist_industry_enrich.py \
  tests/test_position_risk_tags.py \
  tests/test_trading_risk.py \
  tests/test_ai_write_positions.py -v
```

Expected: router 行数 `<280`（若略超但明显薄于 513 且无业务逻辑可接受，在报告说明）；`ok`；PASS

- [ ] **Step 7: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(watchlist): 胖 API 拆入 domains service 与薄 router

自选/持仓/信号/行情视图离开 router；trading_risk 同域；旧路径兼容壳保留。
EOF
)"
```

---

### Task 4: README + 相关回归

**Files:**
- Modify: `backend/app/domains/README.md`

- [ ] **Step 1:** 在「已迁入」追加 `- watchlist（自选/分组/持仓/信号面板/trading_risk，Phase 3）`

- [ ] **Step 2: 回归**

```bash
cd backend && uv run pytest \
  tests/test_app_errors.py \
  tests/test_watchlist_groups.py \
  tests/test_watchlist_industry_enrich.py \
  tests/test_positions.py \
  tests/test_signal_panel.py \
  tests/test_position_risk_tags.py \
  tests/test_trading_risk.py \
  tests/test_strategy_signal_ma.py \
  tests/test_auth_api.py \
  tests/test_channels_api.py -v
```

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(domains): 标注 watchlist 域已迁入

与 Phase 3 落地同步。
EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| watchlist 垂直切片 | Task 2–3 |
| 拆大文件 / 路由可控 | Task 3 |
| AppError 边界 | Task 1–3 |
| 兼容壳 | Task 2–3 |

## Out of scope

- 迁 `strategy_board` / signal 启发式大文件
- 拆 `ai_tools`
- 拆除兼容壳
- 改前端
