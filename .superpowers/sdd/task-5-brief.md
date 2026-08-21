### Task 5: watchlist + content + plan 拆壳

**Files 删除（13 个 shim）：**
- `app/repositories/watchlist.py`、`app/repositories/positions.py`、`app/repositories/signal_panel.py`
- `app/schemas/watchlist.py`、`app/schemas/content.py`
- `app/services/content/` 整目录（notes/feed/notify_log + `__init__.py`）
- `app/services/plan/` 整目录（playbook/trading_risk + `__init__.py`）
- `app/api/v1/watchlist.py`、`app/api/v1/content.py`

**改消费者（先改后删）：**

1. 仓库类（映射：`app.repositories.{watchlist,positions,signal_panel}` → `app.domains.watchlist.{repository,positions_repo,signal_panel_repo}`）：
   - 标准风格：`patch("app.repositories.positions.PositionRepository.*")` → `patch("app.domains.watchlist.positions_repo.PositionRepository.*")`；`app.repositories.signal_panel.SignalPanelRepository` → `app.domains.watchlist.signal_panel_repo.SignalPanelRepository`；`app.repositories.signal_panel` 模块级 import → `app.domains.watchlist.signal_panel_repo`；`app.repositories.watchlist.*` → `app.domains.watchlist.repository.*`
   - 多行风格（`from app.repositories import positions as positions_repo` 等）：
     - `app/services/strategy/strategy_board.py:14-16`：`from app.repositories import positions as positions_repo` → `from app.domains.watchlist import positions_repo`（模块名一致，删别名）；`signal_panel_repo` 同理；`from app.repositories import watchlist as repo` → `from app.domains.watchlist import repository as repo`
     - `app/services/ai/ai_tools.py:13-15`：positions_repo/signal_panel_repo 同上；`watchlist as watchlist_repo` → `from app.domains.watchlist import repository as watchlist_repo`
     - `app/services/team/team_prefetch.py:11`：`watchlist as watchlist_repo` → 同上
2. schemas：
   - `app.schemas.watchlist` → `app.domains.watchlist.schemas`（tests/test_ai_read_tools.py、test_ai_write_positions.py、test_suspend_filter.py）
   - `app.schemas.content` → `app.domains.content.schemas`（tests/test_team_reports.py、app/services/team/team_reports.py）
3. content services：
   - `from app.services.content import notes` → `from app.domains.content import notes`（app/services/ai/ai_tools.py:16、ai_read_tools.py:21）
   - `from app.services.content.notify_log import ...` → `from app.domains.content.notify_log import ...`（tests/test_notify_log.py）
4. plan：
   - `from app.services.plan.trading_risk import ...` → `from app.domains.watchlist.trading_risk import ...`（strategy_board.py:18）
   - `from app.services.plan import trading_risk` → `from app.domains.watchlist import trading_risk`（ai_read_tools.py:24）
   - `from app.services.plan import trading_risk as tr` → `from app.domains.watchlist import trading_risk as tr`（tests/test_trading_risk.py）
5. `app/api/v1/__init__.py`：watchlist/content router 直连 `from app.domains.watchlist.router import router as watchlist_router`、`from app.domains.content.router import router as content_router`，从 `from app.api.v1 import (...)` 元组移除 watchlist、content。

**其它：** `app/repositories/__init__.py` docstring 里 `from app.repositories import watchlist` 示例行删除或改写（watchlist 已迁 domains）；`app/services/content`、`app/services/plan` 目录删除后无残留消费。

**删除后残留扫描必须零命中：**
```bash
cd backend && rg "app.repositories.watchlist|app.repositories.positions|app.repositories.signal_panel|app.schemas.watchlist|app.services.content|app.schemas.content|app.services.plan|app.api.v1.watchlist|app.api.v1.content" app tests --glob '*.py'
```
（注意：`app.services.plan` pattern 也可能命中 docstring，统一处理）

**测试：**
```bash
cd backend && uv run pytest -q --tb=short
```
全量绿才提交（预计 713+）。

**Commit**（简体中文 HEREDOC）：
`refactor(domains): 拆除 watchlist/content/plan 域兼容壳`

**Report** → `/Users/xiezhigang/Projects/me/zak2/.worktrees/backend-domains-phase6/.superpowers/sdd/task-5-report.md`

**禁止：** 改 REST 路径/算法；改 domains 实现；删其它域 shim（backtest/auto_schedules 属 Task 6）。
