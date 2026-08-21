# Task 5 Report: watchlist + content + plan 拆壳

## Status

✅ 完成（commit `f057a53`）

## Commits

- `f057a53` `refactor(domains): 拆除 watchlist/content/plan 域兼容壳`

## Changes

**删除 14 个 shim 文件（git rm）：**

- `app/repositories/{watchlist,positions,signal_panel}.py`
- `app/schemas/{watchlist,content}.py`
- `app/services/content/`（`__init__/notes/feed/notify_log`）
- `app/services/plan/`（`__init__/playbook/trading_risk`）
- `app/api/v1/{watchlist,content}.py`

**改消费者（10 个 app 文件 + 7 个 tests 文件）：**

- `strategy_board.py`：positions/signal_panel/watchlist 仓库与 trading_risk 全部改走 `app.domains.watchlist.*`
- `ai_tools.py` / `ai_read_tools.py`：positions_repo、signal_panel_repo、watchlist_repo、notes、trading_risk → `app.domains.*`（保留 `backtest_repo` 供 Task 6）
- `team_prefetch.py`：watchlist_repo → `app.domains.watchlist.repository`
- `team_reports.py`、`test_team_reports.py`：schemas.content → `app.domains.content.schemas`
- `test_notify_log.py`：notify_log → `app.domains.content.notify_log`
- `test_signal_panel.py`：→ `app.domains.watchlist.signal_panel_repo`
- `test_trading_risk.py`：→ `app.domains.watchlist.trading_risk`
- `test_ai_read_tools.py` / `test_ai_write_positions.py` / `test_suspend_filter.py`：patch 目标与 schemas → `app.domains.watchlist.*`
- `app/api/v1/__init__.py`：watchlist/content router 直连 domains，从 `from app.api.v1 import (...)` 元组移除
- `app/repositories/__init__.py`：docstring 中 watchlist 示例行替换为 `app.repositories.chat`

**禁止项核验：** REST 路径/算法未改；domains 实现未动；backtest/auto_schedules shim 保留（Task 6）。

## Tests

- 残留扫描：`rg "app.repositories.watchlist|...|app.api.v1.content" app tests --glob '*.py'` 零命中
- 全量回归：`uv run pytest -q --tb=short` → **713 passed** ✅

## Concerns

- 无。期间一次编辑误删 `ai_read_tools.py` 中 `screener_repo` 导入，已立即补回并复核。
